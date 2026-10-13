import datetime
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from game import apple
from game.models import AppUser, Completion

TMP = Path(tempfile.mkdtemp())
(TMP / "2026-10-14.json").write_text(json.dumps({"date": "2026-10-14", "puzzles": []}))
(TMP / "index.json").write_text(json.dumps({"dates": ["2026-10-14"]}))


def sign_in(client, sub="apple-user-1"):
    with mock.patch.object(apple, "verify_identity_token", return_value={"sub": sub, "email": "a@b.c"}):
        r = client.post("/api/auth/apple", json.dumps({"identity_token": "x"}), content_type="application/json")
    return r.json()["token"], r


@override_settings(PUZZLE_DIR=TMP)
class ApiTests(TestCase):
    def auth(self, token):
        return {"HTTP_AUTHORIZATION": "Bearer " + token}

    def post(self, path, data, token=None):
        return self.client.post(path, json.dumps(data), content_type="application/json",
                                **(self.auth(token) if token else {}))

    def test_daily_files(self):
        r = self.client.get("/api/daily/2026-10-14")
        self.assertEqual(r.status_code, 200)
        self.assertIn("max-age", r["Cache-Control"])
        self.assertEqual(self.client.get("/api/daily/2026-10-15").status_code, 404)
        self.assertEqual(self.client.get("/api/daily/..%2Fsecret").status_code, 404)   # never reaches the file system
        self.assertEqual(self.client.get("/api/daily/abc").status_code, 400)
        self.assertEqual(self.client.get("/api/daily/index").json()["dates"], ["2026-10-14"])

    def test_bad_apple_token_rejected(self):
        with mock.patch.object(apple, "verify_identity_token", side_effect=apple.AppleAuthError("bad")):
            r = self.post("/api/auth/apple", {"identity_token": "forged"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(AppUser.objects.count(), 0)

    def test_sign_in_is_idempotent(self):
        t1, r1 = sign_in(self.client)
        t2, r2 = sign_in(self.client)
        self.assertTrue(r1.json()["new_user"])
        self.assertFalse(r2.json()["new_user"])
        self.assertEqual(AppUser.objects.count(), 1)

    def test_endpoints_need_auth(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(self.post("/api/completions", {}).status_code, 401)
        self.assertEqual(self.client.get("/api/me", HTTP_AUTHORIZATION="Bearer garbage").status_code, 401)

    def test_completion_keeps_best_time_and_streak(self):
        token, _ = sign_in(self.client)
        today = datetime.date.today()
        for back in (0, 1, 2, 4):          # gap on day 3 ends the streak at 3
            d = (today - datetime.timedelta(days=back)).isoformat()
            r = self.post("/api/completions", {"date": d, "level": 1, "seconds": 100}, token)
            self.assertEqual(r.status_code, 200)
        r = self.post("/api/completions", {"date": today.isoformat(), "level": 1, "seconds": 60, "hints": 1}, token)
        self.assertFalse(r.json()["first_time"])
        r = self.post("/api/completions", {"date": today.isoformat(), "level": 1, "seconds": 300}, token)
        row = Completion.objects.get(date=today, level=1)
        self.assertEqual(row.seconds, 60)                     # slower replay did not overwrite the best
        stats = self.client.get("/api/me", **self.auth(token)).json()["stats"]
        self.assertEqual(stats["current_streak"], 3)
        self.assertEqual(stats["best_streak"], 3)
        self.assertEqual(stats["by_level"]["1"]["best_seconds"], 60)

    def test_validation(self):
        token, _ = sign_in(self.client)
        for bad in ({"date": "2026-10-14", "level": 9, "seconds": 5}, {"date": "nope", "level": 1, "seconds": 5},
                    {"date": "2026-10-14", "level": 1, "seconds": 0}, {"date": "2999-01-01", "level": 1, "seconds": 5}):
            self.assertEqual(self.post("/api/completions", bad, token).status_code, 400, bad)

    def test_leaderboard_hides_unnamed_and_hinted(self):
        ta, _ = sign_in(self.client, "a")
        tb, _ = sign_in(self.client, "b")
        tc, _ = sign_in(self.client, "c")
        d = datetime.date.today().isoformat()
        self.client.patch("/api/me", json.dumps({"display_name": "Zed"}), content_type="application/json", **self.auth(ta))
        self.client.patch("/api/me", json.dumps({"display_name": "Amy"}), content_type="application/json", **self.auth(tb))
        self.post("/api/completions", {"date": d, "level": 2, "seconds": 90}, ta)
        self.post("/api/completions", {"date": d, "level": 2, "seconds": 50, "hints": 1}, tb)   # used a hint
        self.post("/api/completions", {"date": d, "level": 2, "seconds": 10}, tc)               # no display name
        entries = self.client.get(f"/api/leaderboard/{d}/2").json()["entries"]
        self.assertEqual(entries, [{"name": "Zed", "seconds": 90}])

    def test_delete_account_removes_everything(self):
        token, _ = sign_in(self.client)
        self.post("/api/completions", {"date": datetime.date.today().isoformat(), "level": 1, "seconds": 70}, token)
        self.assertEqual(self.client.delete("/api/me", **self.auth(token)).status_code, 200)
        self.assertEqual(AppUser.objects.count(), 0)
        self.assertEqual(Completion.objects.count(), 0)
        self.assertEqual(self.client.get("/api/me", **self.auth(token)).status_code, 401)
