

def test_help(cmd):
    cmd.run_ok([], """
        *testrun management*
    """)


def test_adduser(cmd):
    cmd.run_ok(["add-email-account", "-h"], """
        *add*e-mail*user*
    """)
