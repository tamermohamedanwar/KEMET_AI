from ops.security_agent_review import inspect_source


def categories(source: str, relative_path: str = "app/security_fixture.py") -> list[str]:
    return [item["category"] for item in inspect_source(source, relative_path)]


def test_safe_argv_subprocess_is_hypothesized_without_shell_execution():
    result = inspect_source("import subprocess\nsubprocess.run([\"echo\", \"ok\"])\n")
    assert any(item["category"] == "command-execution" for item in result)
    assert not any(item["category"] == "shell-execution" for item in result)
    assert all(item["execution_authority"] is False for item in result)


def test_shell_true_is_explicitly_detected():
    result = inspect_source("import subprocess\nsubprocess.run(\"echo ok\", shell=True)\n")
    assert "command-execution" in categories("import subprocess\nsubprocess.run(\"echo ok\", shell=True)\n")
    assert "shell-execution" in categories("import subprocess\nsubprocess.run(\"echo ok\", shell=True)\n")


def test_dynamic_code_deserialization_and_yaml_are_detected():
    source = (
        "import pickle\nimport yaml\n"
        "pickle.loads(value)\n"
        "yaml.load(value)\n"
        "eval(value)\n"
        "exec(value)\n"
    )
    result = categories(source)
    assert "unsafe-deserialization" in result
    assert "unsafe-yaml" in result
    assert "dynamic-code" in result


def test_template_csrf_expression_is_not_a_secret_finding():
    source = 'CSRF_TOKEN = "{{ csrf_token }}"\n'
    assert "possible-hardcoded-secret" not in categories(source)


def test_fixture_credentials_are_classified_not_promoted():
    source = 'TEST_PASSWORD = "Capacity-Synthetic-2026!"\n'
    result = inspect_source(source, "tests/fixtures/security_fixture.py")
    assert "test-fixture-secret" in [item["category"] for item in result]
    assert all(item["validation_status"] == "hypothesis" for item in result)


def test_hypothesis_ids_are_deterministic_and_evidence_bound():
    source = "value = eval(user_value)\n"
    first = inspect_source(source)[0]
    second = inspect_source(source)[0]
    assert first["hypothesis_id"] == second["hypothesis_id"]
    assert first["source_digest"]
    assert first["evidence_digest"]
    assert first["caller_symbol"] is None
