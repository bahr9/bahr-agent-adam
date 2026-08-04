# -*- coding: utf-8 -*-
"""
Tests First -- fail-closed للـ endpoints العامة (أوديت 2026-08-04).

الشكل القديم `if secret and token != secret` كان بيتخطى التحقق بالكامل
لو متغير السر مش متظبط -- يعني انجراف بيئة واحد = الـ endpoint مفتوح
على الإنترنت. الاختبارات دي بتثبّت السلوك الجديد: سر غايب = 503 رفض.

بتشتغل على Flask test client محليًا -- صفر شبكة وصفر production.
"""
import os


def run_test(name, fn):
    try:
        fn()
        print(f"OK  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception as e:
        print(f"FAIL {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    os.environ.setdefault("SKIP_BOT_POLLING", "1")
    from main import flask_app

    client = flask_app.test_client()
    results = []

    PROTECTED = [
        ("GET", "/agent-tasks/pending?target=test", "AGENT_TASKS_SECRET", None),
        ("POST", "/agent-tasks/some-id/status", "AGENT_TASKS_SECRET", {"status": "done"}),
        ("POST", "/log-eye-expert", "EYE_EXPERT_SECRET", {"question": "q", "answer": "a"}),
    ]

    def _call(method, path, headers=None, json_body=None):
        if method == "GET":
            return client.get(path, headers=headers or {})
        return client.post(path, headers=headers or {}, json=json_body or {})

    def missing_secret_refuses_with_503():
        for method, path, env_var, body in PROTECTED:
            old = os.environ.pop(env_var, None)
            try:
                r = _call(method, path, json_body=body)
                assert r.status_code == 503, f"{path} رد {r.status_code} بدل 503 والسر غايب"
            finally:
                if old is not None:
                    os.environ[env_var] = old

    def wrong_token_is_401():
        for method, path, env_var, body in PROTECTED:
            old = os.environ.get(env_var)
            os.environ[env_var] = "correct-secret-for-test"
            try:
                r = _call(method, path, headers={"X-Secret-Token": "wrong"}, json_body=body)
                assert r.status_code == 401, f"{path} رد {r.status_code} بدل 401"
            finally:
                if old is None:
                    os.environ.pop(env_var, None)
                else:
                    os.environ[env_var] = old

    def no_token_is_401_when_configured():
        for method, path, env_var, body in PROTECTED:
            old = os.environ.get(env_var)
            os.environ[env_var] = "correct-secret-for-test"
            try:
                r = _call(method, path, json_body=body)
                assert r.status_code == 401, f"{path} رد {r.status_code} بدل 401"
            finally:
                if old is None:
                    os.environ.pop(env_var, None)
                else:
                    os.environ[env_var] = old

    def health_stays_public():
        assert client.get("/health").status_code == 200, "الـ health لازم يفضل عام"

    for name, fn in [
        ("سر غايب = 503 رفض مش فتح", missing_secret_refuses_with_503),
        ("توكن غلط = 401", wrong_token_is_401),
        ("من غير توكن = 401", no_token_is_401_when_configured),
        ("الـ health عام زي ما هو", health_stays_public),
    ]:
        results.append(run_test(name, fn))

    print()
    if all(results):
        print(f"{len(results)}/{len(results)} اختبار عدّى")
    else:
        print(f"{sum(results)}/{len(results)} بس اللي عدّى")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
