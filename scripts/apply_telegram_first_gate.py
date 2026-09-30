from pathlib import Path

p = Path("app/services/final_content_approval_service.py")
s = p.read_text()
old = '        required_platforms = {"youtube"}\n        optional_platforms = set(selected) - required_platforms\n'
new = '        required_platforms = {"telegram"}\n        optional_platforms = set(selected) - {"telegram"}\n'
if old not in s:
    raise SystemExit("target_not_found_final_service")
p.write_text(s.replace(old, new, 1))

p = Path("tests/kemet/test_final_content_approval_service.py")
s = p.read_text()
s = s.replace('        assert "connect_and_verify:youtube" in preflight["next_actions"]\n',
              '        assert "connect_and_verify:youtube" not in preflight["next_actions"]\n')
p.write_text(s)
print("TELEGRAM_FIRST_GATE_APPLIED")
