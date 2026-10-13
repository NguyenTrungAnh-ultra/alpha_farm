import sys
import io
import pytest

class Tee:
    def __init__(self, stream1, stream2):
        self.stream1 = stream1
        self.stream2 = stream2
    def write(self, data):
        self.stream1.write(data)
        self.stream2.write(data)
    def flush(self):
        self.stream1.flush()
        self.stream2.flush()
    def isatty(self):
        return False

def main():
    log_file = 'f:/Projects/alpha_farm/.agents/challenger_m3_2/test_output.log'
    print(f"Running verification runner and logging to {log_file}...")

    buffer = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    tee_out = Tee(old_stdout, buffer)
    tee_err = Tee(old_stderr, buffer)

    sys.stdout = tee_out
    sys.stderr = tee_err

    test_targets = [
        'tests/test_core_engine.py',
        'f:/Projects/alpha_farm/.agents/challenger_m3_2/test_challenger_m3_2_verification.py',
    ]

    try:
        exit_code = pytest.main(test_targets + ['-v', '-s'])
        print(f"\nPytest Exit Code: {exit_code}")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(buffer.getvalue())

    print(f"Done! Results written to {log_file}")

if __name__ == '__main__':
    main()
