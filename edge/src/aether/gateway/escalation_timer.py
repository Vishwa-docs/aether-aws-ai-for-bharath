"""
AETHER Edge-Local Escalation Timer
=====================================
Manages escalation timers on the edge device so critical alerts progress
even when the cloud is unreachable.

Escalation ladder (runs entirely on-edge):
  Tier 1: Local voice prompt + chime (0 s)
  Tier 2: Family caregiver push/SMS via local queue (60 s)
  Tier 3: Secondary caregiver + neighbor beacon (180 s)
  Tier 4: Nurse hotline / telehealth (300 s)
  Tier 5: Emergency services handoff packet (600 s)

Each tier is attempted locally first. When cloud connectivity is restored,
all escalation actions are synced and the cloud takes over.

The escalation continues autonomously even if cloud is completely
offline — this is the "Safety Loop" from the AETHER spec.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from aether.models.schemas import (
    AetherEvent,
    EscalationInfo,
    Severity,
)

logger = logging.getLogger("aether.gateway.escalation")


# ─── Escalation Configuration ────────────────────────────────

class EscalationTier(int, Enum):
    VOICE_PROMPT = 1
    FAMILY_NOTIFY = 2
    SECONDARY_CONTACTS = 3
    NURSE_HOTLINE = 4
    EMERGENCY_SERVICES = 5


@dataclass
class EscalationContact:
    """A contact in the escalation chain."""
    name: str
    role: str               # "family", "neighbor", "nurse", "emergency"
    phone: str
    tier: EscalationTier
    priority: int = 0       # lower = higher priority within tier


@dataclass
class EscalationAction:
    """Record of an escalation action taken."""
    action_id: str
    tier: EscalationTier
    timestamp: float
    action_type: str         # "voice_prompt", "sms", "siren", "beacon", "call"
    target: str
    success: bool
    details: str = ""


@dataclass
class EscalationState:
    """Tracks the current state of an active escalation."""
    escalation_id: str
    event_id: str
    event_type: str
    severity: str
    started_at: float
    current_tier: EscalationTier
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None
    cancelled: bool = False
    cancelled_reason: str = ""
    actions: List[EscalationAction] = field(default_factory=list)
    resolved_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["current_tier"] = self.current_tier.value
        d["actions"] = [asdict(a) for a in self.actions]
        return d


# ─── Default tier timing ─────────────────────────────────────

DEFAULT_TIER_DELAYS: Dict[EscalationTier, float] = {
    EscalationTier.VOICE_PROMPT: 0,        # Immediate
    EscalationTier.FAMILY_NOTIFY: 60,      # 60 seconds
    EscalationTier.SECONDARY_CONTACTS: 180, # 3 minutes
    EscalationTier.NURSE_HOTLINE: 300,     # 5 minutes
    EscalationTier.EMERGENCY_SERVICES: 600, # 10 minutes
}

# Severity-adjusted delays (critical events escalate faster)
CRITICAL_TIER_DELAYS: Dict[EscalationTier, float] = {
    EscalationTier.VOICE_PROMPT: 0,
    EscalationTier.FAMILY_NOTIFY: 30,
    EscalationTier.SECONDARY_CONTACTS: 90,
    EscalationTier.NURSE_HOTLINE: 150,
    EscalationTier.EMERGENCY_SERVICES: 300,
}


# ─── Escalation Timer ────────────────────────────────────────

class EdgeEscalationTimer:
    """Edge-local escalation timer for critical events.

    This runs autonomously on the edge device and does NOT depend on
    cloud connectivity. It uses local actions (voice prompts, sirens,
    queued notifications) to escalate emergencies.

    Parameters
    ----------
    contacts : list[EscalationContact]
        Ordered list of escalation contacts.
    tier_delays : dict or None
        Override default tier timing. Maps EscalationTier → seconds.
    on_action : callable or None
        Callback invoked for each escalation action:
        ``on_action(state, action)``.
    siren_enabled : bool
        Whether to activate local siren at tier 3+.
    """

    def __init__(
        self,
        contacts: Optional[List[EscalationContact]] = None,
        tier_delays: Optional[Dict[EscalationTier, float]] = None,
        on_action: Optional[Callable[["EscalationState", "EscalationAction"], None]] = None,
        siren_enabled: bool = True,
    ):
        self._contacts = contacts or _default_contacts()
        self._tier_delays = tier_delays or dict(DEFAULT_TIER_DELAYS)
        self._on_action = on_action
        self._siren_enabled = siren_enabled

        self._active_escalations: Dict[str, EscalationState] = {}
        self._history: List[EscalationState] = []

    # ── Start escalation ──────────────────────────────────────

    def start_escalation(self, event: AetherEvent) -> EscalationState:
        """Start a new escalation for an event.

        Returns the initial EscalationState.
        """
        esc_id = uuid.uuid4().hex[:12]
        now = time.time()

        # Use faster timing for critical events
        if event.severity in (Severity.CRITICAL,):
            tier_delays = dict(CRITICAL_TIER_DELAYS)
        else:
            tier_delays = dict(self._tier_delays)

        state = EscalationState(
            escalation_id=esc_id,
            event_id=event.event_id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            started_at=now,
            current_tier=EscalationTier.VOICE_PROMPT,
        )

        self._active_escalations[esc_id] = state

        # Execute tier 1 immediately
        self._execute_tier(state, EscalationTier.VOICE_PROMPT)

        logger.info(
            "Escalation started: id=%s event=%s severity=%s",
            esc_id, event.event_id, event.severity.value,
        )

        return state

    # ── Acknowledge / Cancel ──────────────────────────────────

    def acknowledge(
        self,
        escalation_id: str,
        acknowledged_by: str = "resident",
    ) -> bool:
        """Mark an escalation as acknowledged (stops further progression)."""
        state = self._active_escalations.get(escalation_id)
        if not state:
            return False

        state.acknowledged = True
        state.acknowledged_by = acknowledged_by
        state.acknowledged_at = time.time()

        logger.info("Escalation %s acknowledged by %s", escalation_id, acknowledged_by)
        self._finalise(state)
        return True

    def cancel(
        self,
        escalation_id: str,
        reason: str = "false_alarm",
    ) -> bool:
        """Cancel an active escalation (e.g., resident confirmed OK)."""
        state = self._active_escalations.get(escalation_id)
        if not state:
            return False

        state.cancelled = True
        state.cancelled_reason = reason
        state.resolved_at = time.time()

        logger.info("Escalation %s cancelled: %s", escalation_id, reason)
        self._finalise(state)
        return True

    # ── Tick (called periodically) ────────────────────────────

    def tick(self) -> List[EscalationAction]:
        """Check all active escalations and advance tiers as needed.

        Should be called periodically (e.g., every 10 seconds).

        Returns list of actions taken during this tick.
        """
        now = time.time()
        actions_taken: List[EscalationAction] = []

        for esc_id, state in list(self._active_escalations.items()):
            if state.acknowledged or state.cancelled:
                continue

            elapsed = now - state.started_at

            # Determine next tier based on elapsed time
            severity = state.severity
            delays = CRITICAL_TIER_DELAYS if severity == "critical" else self._tier_delays

            for tier in EscalationTier:
                tier_delay = delays.get(tier, float("inf"))
                if elapsed >= tier_delay and tier.value > state.current_tier.value:
                    action = self._execute_tier(state, tier)
                    state.current_tier = tier
                    if action:
                        actions_taken.append(action)

            # If we've reached the final tier and enough time has passed, finalize
            if (
                state.current_tier == EscalationTier.EMERGENCY_SERVICES
                and elapsed > delays[EscalationTier.EMERGENCY_SERVICES] + 300
            ):
                state.resolved_at = now
                self._finalise(state)

        return actions_taken

    # ── Internal ──────────────────────────────────────────────

    def _execute_tier(
        self,
        state: EscalationState,
        tier: EscalationTier,
    ) -> Optional[EscalationAction]:
        """Execute escalation actions for a given tier."""
        now = time.time()

        if tier == EscalationTier.VOICE_PROMPT:
            action = EscalationAction(
                action_id=uuid.uuid4().hex[:8],
                tier=tier,
                timestamp=now,
                action_type="voice_prompt",
                target="resident",
                success=True,
                details="Are you okay? Say 'I'm fine' or press the OK button to cancel this alert.",
            )
        elif tier == EscalationTier.FAMILY_NOTIFY:
            contacts = [c for c in self._contacts if c.tier == tier]
            target = contacts[0].name if contacts else "family"
            action = EscalationAction(
                action_id=uuid.uuid4().hex[:8],
                tier=tier,
                timestamp=now,
                action_type="sms",
                target=target,
                success=True,
                details=f"AETHER Alert: {state.event_type} detected for your family member. "
                        f"Severity: {state.severity}. Please check in.",
            )
        elif tier == EscalationTier.SECONDARY_CONTACTS:
            contacts = [c for c in self._contacts if c.tier == tier]
            target = ", ".join(c.name for c in contacts) if contacts else "neighbors"
            action = EscalationAction(
                action_id=uuid.uuid4().hex[:8],
                tier=tier,
                timestamp=now,
                action_type="beacon" if self._siren_enabled else "sms",
                target=target,
                success=True,
                details="Neighbor beacon activated" if self._siren_enabled else "SMS sent to secondary contacts",
            )
            if self._siren_enabled:
                logger.warning("SIREN ACTIVATED for escalation %s", state.escalation_id)
        elif tier == EscalationTier.NURSE_HOTLINE:
            contacts = [c for c in self._contacts if c.tier == tier]
            target = contacts[0].name if contacts else "nurse_hotline"
            action = EscalationAction(
                action_id=uuid.uuid4().hex[:8],
                tier=tier,
                timestamp=now,
                action_type="call",
                target=target,
                success=True,
                details="Automated call to nurse hotline with event summary",
            )
        elif tier == EscalationTier.EMERGENCY_SERVICES:
            action = EscalationAction(
                action_id=uuid.uuid4().hex[:8],
                tier=tier,
                timestamp=now,
                action_type="call",
                target="emergency_services",
                success=True,
                details="Emergency services contacted with location and evidence packet",
            )
            logger.critical(
                "EMERGENCY SERVICES CONTACTED for escalation %s (event: %s)",
                state.escalation_id, state.event_id,
            )
        else:
            return None

        state.actions.append(action)

        if self._on_action:
            try:
                self._on_action(state, action)
            except Exception as exc:
                logger.warning("Escalation action callback error: %s", exc)

        logger.info(
            "Escalation %s → Tier %d (%s → %s)",
            state.escalation_id, tier.value, action.action_type, action.target,
        )
        return action

    def _finalise(self, state: EscalationState) -> None:
        """Move escalation from active to history."""
        self._active_escalations.pop(state.escalation_id, None)
        self._history.append(state)

    # ── Properties ────────────────────────────────────────────

    @property
    def active_escalations(self) -> List[EscalationState]:
        return list(self._active_escalations.values())

    @property
    def escalation_history(self) -> List[EscalationState]:
        return list(self._history)

    @property
    def active_count(self) -> int:
        return len(self._active_escalations)


# ── Default contacts ──────────────────────────────────────────

def _default_contacts() -> List[EscalationContact]:
    return [
        EscalationContact(
            name="Priya Sharma", role="family", phone="+91-98765-43210",
            tier=EscalationTier.FAMILY_NOTIFY, priority=0,
        ),
        EscalationContact(
            name="Rahul Mehta", role="family", phone="+91-98765-43211",
            tier=EscalationTier.FAMILY_NOTIFY, priority=1,
        ),
        EscalationContact(
            name="Mrs. Gupta (Neighbor)", role="neighbor", phone="+91-98765-43212",
            tier=EscalationTier.SECONDARY_CONTACTS, priority=0,
        ),
        EscalationContact(
            name="AETHER Nurse Hotline", role="nurse", phone="1800-AETHER",
            tier=EscalationTier.NURSE_HOTLINE, priority=0,
        ),
        EscalationContact(
            name="Emergency Services", role="emergency", phone="112",
            tier=EscalationTier.EMERGENCY_SERVICES, priority=0,
        ),
    ]
