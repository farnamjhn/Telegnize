"""Runs the decision engine over a chat's messages and aggregates the answers.

A full pass is expensive, and how expensive is not predictable from here: it is
local inference, the multilingual checkpoint that non-Latin text routes to is
slower than the English one, and a machine under sustained load throttles. Two
things that used to dominate a run no longer do — the engine keeps both routed
checkpoints resident rather than rebuilding one whenever the script changes,
and text a previous message already said is answered once — but what is left is
still a forward pass per message. A page is put to the engine as one batch, so
those passes can share work, but measure a small page on the target hardware
before starting a long run.

So assessment is paged and resumable: each call works through one page, skips
anything already answered, and reports where to pick up. Answers land in the
decision cache, and the aggregate is computed from whatever is in there. There
is no need to assess a whole chat — a few hundred messages is enough to read a
rate off, and every aggregate is reported against its coverage.
"""

import logging
from collections.abc import Mapping, Sequence

from application.decision_questions import ASSESSMENT_QUESTIONS, RESPONSE_QUESTIONS
from application.dtos.analysis_dto import (
    AssessmentProgressDTO,
    ParticipantAssessmentDTO,
    RelationalAssessmentDTO,
)
from application.ports.decision_engine import IDecisionEngine
from domain.errors import ChatNotFoundError
from domain.models.analysis import Decision, DecisionTarget
from domain.models.message import Message
from domain.repository.chat_repository import IChatRepository
from domain.repository.decision_repository import IDecisionRepository
from domain.repository.message_repository import IMessageRepository

logger = logging.getLogger(__name__)

#: Messages assessed per call. Deliberately small: a page is a blocking run of
#: the question set per message, and per-message cost varies by an order of
#: magnitude across languages and machines. Raise it once you have timed a page
#: on the hardware it will run on.
DEFAULT_PAGE_SIZE = 25

#: The question whose presence marks a message as assessed.
_COVERAGE_KEY = "valence"
#: Where the answer to "did the reply engage with this?" is filed. It is stored
#: against the bid rather than the reply, so a participant's met-bid rate is a
#: plain group-by over their own messages.
_BID_MET_KEY = "bid_met"

_TRUE = "true"


class AssessmentService:
    def __init__(
        self,
        chat_repo: IChatRepository,
        message_repo: IMessageRepository,
        decision_repo: IDecisionRepository,
        engine: IDecisionEngine,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self._chats = chat_repo
        self._messages = message_repo
        self._decisions = decision_repo
        self._engine = engine
        self._page_size = page_size

    # --- running ----------------------------------------------------------
    def assess_page(
        self,
        chat_id: int,
        offset: int = 0,
        limit: int | None = None,
    ) -> AssessmentProgressDTO:
        """Assesses one page of a chat's messages, oldest first.

        Raises:
            ChatNotFoundError: if the chat has not been imported.
            DecisionEngineError: if the engine fails.
        """
        chat = self._chats.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)

        page_size = limit or self._page_size
        page = self._messages.list_messages(
            chat_id=chat_id, limit=page_size, offset=offset
        )
        already_done = self._decisions.answered_message_ids(
            [message.id for message in page], _COVERAGE_KEY
        )

        pending = [
            (position, message)
            for position, message in enumerate(page)
            if message.id not in already_done and message.analysis_text.strip()
        ]
        self._assess_messages(pending, page)
        assessed = len(pending)

        total = self._messages.count_by_chat(chat_id)
        next_offset = offset + len(page)
        logger.info(
            "Assessed %d of %d messages in page at offset %d of chat %s.",
            assessed, len(page), offset, chat_id,
        )
        return AssessmentProgressDTO(
            chat_id=chat_id,
            assessed_now=assessed,
            skipped_already_done=len(already_done),
            next_offset=next_offset,
            is_complete=len(page) < page_size or next_offset >= total,
            coverage_percent=self._coverage(chat_id, total),
        )

    def _assess_messages(
        self,
        pending: Sequence[tuple[int, Message]],
        page: Sequence[Message],
    ) -> None:
        """Answers the question set about each pending message, then about the
        replies to whichever of them turned out to be bids.

        Two batched calls rather than one or two per message: the engine can
        share forward passes between the states in a batch, which a loop of
        single predictions never lets it do. The second batch has to wait on
        the first, because only a bid's reply is put to the engine.
        """
        if not pending:
            return

        results = self._engine.predict_batch(
            [
                {"sender": message.sender_name, "text": message.analysis_text}
                for _, message in pending
            ],
            ASSESSMENT_QUESTIONS,
        )

        decisions: list[Decision] = []
        bids: list[tuple[Message, Message]] = []
        for (position, message), result in zip(pending, results, strict=True):
            decisions.extend(
                Decision(
                    target_type=DecisionTarget.MESSAGE,
                    target_id=message.id,
                    question_key=answer.question_key,
                    decision_type=answer.decision_type,
                    result_value=answer.value,
                    confidence=answer.confidence,
                    probabilities=answer.probabilities,
                    engine_metadata=result.metadata,
                )
                for answer in result.answers.values()
            )
            bid = result.answers.get("is_bid")
            reply = _next_from_another_sender(message, page[position + 1 :])
            if bid is not None and bid.value and reply is not None:
                bids.append((message, reply))

        decisions.extend(self._assess_replies(bids))
        self._decisions.save_batch(decisions)

    def _assess_replies(
        self, pairs: Sequence[tuple[Message, Message]]
    ) -> list[Decision]:
        """Asks, for each (bid, reply), whether the reply turned toward the bid."""
        if not pairs:
            return []
        results = self._engine.predict_batch(
            [
                {
                    "previous_message": bid.analysis_text,
                    "response": reply.analysis_text,
                }
                for bid, reply in pairs
            ],
            RESPONSE_QUESTIONS,
        )
        decisions = []
        for (bid, reply), result in zip(pairs, results, strict=True):
            answer = result.answers["turns_toward"]
            decisions.append(
                Decision(
                    target_type=DecisionTarget.MESSAGE,
                    target_id=bid.id,
                    question_key=_BID_MET_KEY,
                    decision_type=answer.decision_type,
                    result_value=answer.value,
                    confidence=answer.confidence,
                    probabilities=answer.probabilities,
                    engine_metadata={
                        **result.metadata,
                        "response_message_id": reply.id,
                    },
                )
            )
        return decisions

    # --- reading ----------------------------------------------------------
    def get_assessment(self, chat_id: int) -> RelationalAssessmentDTO:
        """Aggregates whatever has been assessed so far.

        Raises:
            ChatNotFoundError: if the chat has not been imported.
        """
        chat = self._chats.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)

        total = self._messages.count_by_chat(chat_id)
        assessed = self._decisions.count_answered_in_chat(chat_id, _COVERAGE_KEY)
        if assessed == 0:
            return RelationalAssessmentDTO(
                chat_id=chat.id, chat_name=chat.name, total_messages=total
            )

        valence = self._decisions.count_values_by_sender(chat_id, _COVERAGE_KEY)
        bids = self._decisions.count_values_by_sender(chat_id, "is_bid")
        bids_met = self._decisions.count_values_by_sender(chat_id, _BID_MET_KEY)
        friction = self._decisions.count_values_by_sender(chat_id, "friction")
        repair = self._decisions.count_values_by_sender(chat_id, "is_repair")
        acts = self._decisions.count_values_by_sender(chat_id, "discourse_act")
        sarcasm = self._decisions.average_value_by_sender(chat_id, "sarcasm")
        totals = {
            str(row["sender_id"]): row
            for row in self._messages.get_participant_totals(chat_id)
        }

        participants = [
            self._participant(
                sender_id,
                sender_name=str(totals.get(sender_id, {}).get("sender_name", sender_id)),
                word_count=int(totals.get(sender_id, {}).get("word_count") or 0),
                valence=counts,
                bids=bids.get(sender_id, {}),
                bids_met=bids_met.get(sender_id, {}),
                friction=friction.get(sender_id, {}),
                repair=repair.get(sender_id, {}),
                acts=acts.get(sender_id, {}),
                sarcasm=sarcasm.get(sender_id),
            )
            for sender_id, counts in valence.items()
        ]
        participants.sort(key=lambda p: p.assessed_message_count, reverse=True)

        return RelationalAssessmentDTO(
            chat_id=chat.id,
            chat_name=chat.name,
            total_messages=total,
            assessed_messages=assessed,
            coverage_percent=_percent(assessed, total),
            participants=participants,
        )

    @staticmethod
    def _participant(
        sender_id: str,
        *,
        sender_name: str,
        word_count: int,
        valence: Mapping[str, int],
        bids: Mapping[str, int],
        bids_met: Mapping[str, int],
        friction: Mapping[str, int],
        repair: Mapping[str, int],
        acts: Mapping[str, int],
        sarcasm: float | None,
    ) -> ParticipantAssessmentDTO:
        assessed = sum(valence.values())
        positive = valence.get("positive", 0)
        negative = valence.get("negative", 0)

        bid_count = bids.get(_TRUE, 0)
        met_count = bids_met.get(_TRUE, 0)
        answered_bids = sum(bids_met.values())

        criticism = friction.get("criticism", 0)
        defensiveness = friction.get("defensiveness", 0)
        contempt = friction.get("contempt", 0)
        repairs = repair.get(_TRUE, 0)
        open_questions = acts.get("open_question_or_vulnerability", 0)

        return ParticipantAssessmentDTO(
            sender_id=sender_id,
            sender_name=sender_name,
            assessed_message_count=assessed,
            positive_count=positive,
            neutral_count=valence.get("neutral", 0),
            negative_count=negative,
            positivity_ratio=round(positive / negative, 2) if negative else None,
            bid_count=bid_count,
            bids_met_count=met_count,
            # Only bids that got a reply at all were put to the engine, so the
            # rate is over those rather than over every bid made.
            bids_met_percent=(
                _percent(met_count, answered_bids) if answered_bids else None
            ),
            criticism_count=criticism,
            defensiveness_count=defensiveness,
            contempt_count=contempt,
            friction_percent=_percent(
                criticism + defensiveness + contempt, assessed
            ),
            repair_count=repairs,
            repair_percent=_percent(repairs, assessed),
            avg_sarcasm_score=round(sarcasm, 2) if sarcasm is not None else None,
            statement_count=acts.get("statement", 0),
            closed_question_count=acts.get("closed_question", 0),
            open_question_count=open_questions,
            curiosity_per_1k_words=(
                round(open_questions / word_count * 1000, 2) if word_count else 0.0
            ),
        )

    def _coverage(self, chat_id: int, total: int) -> float:
        answered = self._decisions.count_answered_in_chat(chat_id, _COVERAGE_KEY)
        return _percent(answered, total)


def _next_from_another_sender(
    message: Message, following: Sequence[Message]
) -> Message | None:
    """The first later message by someone else, if it is in this page.

    A bid at the very end of a page has its reply on the next page and is left
    unlinked; the next pass over that range picks it up.
    """
    for candidate in following:
        if candidate.sender_id != message.sender_id:
            return candidate if candidate.analysis_text.strip() else None
    return None


def _percent(part: float, whole: float) -> float:
    return round(part / whole * 100, 2) if whole else 0.0
