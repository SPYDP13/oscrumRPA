import os
import tempfile
from datetime import datetime

import certifi
from requests.adapters import HTTPAdapter
from exchangelib import Account, Configuration, Credentials, DELEGATE, EWSDateTime, EWSTimeZone
from exchangelib.protocol import BaseProtocol

from app_paths import resource
from config import EXCHANGE_SERVER, EXCHANGE_EMAIL, EXCHANGE_USERNAME, EXCHANGE_PASSWORD
from dateformat import date_simple, date_str

# Le serveur Exchange n'envoie pas son certificat intermédiaire (Sectigo DV R36) : on l'ajoute
# aux autorités de certifi pour que la vérification SSL passe (sans la désactiver).
_INTERMEDIATE = resource("certs", "sectigo-public-server-auth-ca-dv-r36.pem")
_CA_BUNDLE = os.path.join(tempfile.gettempdir(), "eprojet-rpa-ca-bundle.pem")


class _CABundleAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        kwargs["verify"] = _CA_BUNDLE
        return super().send(request, **kwargs)


def _install_ca_bundle():
    with open(_CA_BUNDLE, "w") as out, open(certifi.where()) as ca, open(_INTERMEDIATE) as inter:
        out.write(ca.read() + "\n" + inter.read())
    BaseProtocol.HTTP_ADAPTER_CLS = _CABundleAdapter


class OutlookCalendarExtractor:
    """
    Lit les réunions du calendrier Outlook (Exchange on-premise, via EWS) entre since et until.

    Réunions ignorées : refusées, annulées, privées, journée entière, "Disponible"/"Absent du bureau",
    et celles du week-end.
    """

    def __init__(self, since: str, until: str):
        """
        since : "2026-10-12T00:00:00Z"
        until : "2026-10-16T23:59:59Z"
        """
        self.since = since
        self.until = until

    # ─────────────────────────────────────────────────────────────
    def _connect(self) -> Account:
        _install_ca_bundle()
        credentials = Credentials(username=EXCHANGE_USERNAME or EXCHANGE_EMAIL, password=EXCHANGE_PASSWORD)
        config = Configuration(server=EXCHANGE_SERVER, credentials=credentials)
        return Account(primary_smtp_address=EXCHANGE_EMAIL, config=config,
                       autodiscover=False, access_type=DELEGATE)

    # ─────────────────────────────────────────────────────────────
    def get_meetings(self) -> list:
        print("\n📆 Récupération des réunions Outlook...")
        account = self._connect()
        tz = account.default_timezone

        def to_ews(s: str) -> EWSDateTime:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            return EWSDateTime.from_datetime(dt.replace(tzinfo=EWSTimeZone("UTC"))).astimezone(tz)

        # view() déplie les réunions récurrentes en occurrences
        items = account.calendar.view(start=to_ews(self.since), end=to_ews(self.until)).only(
            "subject", "start", "end", "is_all_day", "is_cancelled", "my_response_type",
            "sensitivity", "legacy_free_busy_status")

        meetings = []
        for ev in items:
            start = ev.start.astimezone(tz)
            end = ev.end.astimezone(tz)
            reason = self._skip_reason(ev, start)
            if reason:
                print(f"  ⏭  {start:%d/%m %H:%M} {ev.subject} ({reason})")
                continue

            hours = round((end - start).total_seconds() / 3600 * 4) / 4  # pas de 0.25h
            if hours <= 0:
                continue

            meetings.append({
                "title": (ev.subject or "Réunion").strip(),
                # mêmes formats que les commits GitLab
                "dateStr": date_str(start),
                "date": date_simple(start),
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "hours": hours,
            })

        meetings.sort(key=lambda m: (datetime.strptime(m["date"].split(" ")[0], "%Y-%m-%d"), m["start"]))

        print(f"✅ {len(meetings)} réunion(s) retenue(s)")
        for m in meetings:
            print(f"  • {m['date'].split(' ')[0]} {m['start']}-{m['end']} [{m['hours']}h] {m['title']}")
        return meetings

    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _skip_reason(ev, start) -> str:
        if ev.is_cancelled:
            return "annulée"
        if ev.is_all_day:
            return "journée entière"
        if ev.my_response_type == "Decline":
            return "refusée"
        if ev.sensitivity == "Private":
            return "privée"
        if ev.legacy_free_busy_status in ("Free", "OOF"):
            return "disponible / absent"
        if start.weekday() >= 5:
            return "week-end"
        return ""


if __name__ == "__main__":
    # Test en lecture seule : python -m taskProvider.outlook.outlookCalendarExtractor
    from taskProvider.gitlab.gitlabLogExtrator import params
    OutlookCalendarExtractor(since=params["since"], until=params["until"]).get_meetings()
