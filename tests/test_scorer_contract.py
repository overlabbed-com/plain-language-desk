"""The scorer subprocess contract (THREAT-MODEL TB5-1).

The service shells out to a scorer with an argv list, never a shell: user
text travels as FILE CONTENT, never as an argument or command string. This
test pins that contract so the TB5-1 verification can actually fail — a
regression to shell=True, os.system, or an argument-routed text fails here.
"""

from pathlib import Path

SCORER = Path(__file__).resolve().parents[1] / "src" / "plain_language_desk" / "scorer.py"


def test_scorer_uses_exec_argv_never_a_shell():
    source = SCORER.read_text()
    assert "create_subprocess_exec(" in source, (
        "the scorer must spawn the scorer script via exec with an argv list")
    for banned in ("shell=True", "os.system", "subprocess.run", "subprocess.Popen"):
        assert banned not in source, f"shell/argument-routed spawn found: {banned}"


def test_exec_argv_carries_only_script_file_and_mode_flags():
    source = SCORER.read_text()
    argv_region = source[source.index("create_subprocess_exec("):]
    argv_region = argv_region[:argv_region.index(")", argv_region.index("(") + 1)]
    args = [a.strip().strip('",') for a in argv_region.split("\n") if a.strip().strip('",')]
    # Positional argv: "python3", the script, the temp file path, the mode
    # flag. Anything beyond must be a stream kwarg, never another argument.
    assert args[1:6] == ["python3", "script", "--file", "fh.name", "--json"], args
    assert all(a.startswith(("stdout=", "stderr=")) for a in args[6:]), args


def test_script_path_comes_from_the_bundle_not_from_request_data():
    source = SCORER.read_text()
    # The script is the active bundle's scorer or the vendored default —
    # never anything derived from user input.
    assert 'str(scorer_path) if scorer_path else str(VENDOR_SCORER)' in source
