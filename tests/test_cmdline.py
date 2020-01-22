

def test_help(cmd):
    cmd.run_ok([], """
        *testrun management*
    """)


def test_adduser(cmd):
    cmd.run_ok(["add", "-h"], """
        *add*e-mail*user*
    """)
