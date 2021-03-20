
def test_mock_refresh(mocker):
    reply_msg = mocker.run_command("/refresh")
    assert reply.text.startswith("✅ scanned for new logins")


def test_mock_info(mocker):
    reply_msg = mocker.run_command("/info")
    assert reply.text.startswith("?? Userbot active on:")


def test_mock_echo_help(mocker):
    reply = mocker.run_command("/help").text.lower()
    assert "/info" in reply
    assert "/refresh" in reply
    assert "/show" in reply
    assert "/help" in reply
    assert "plugins: " in reply
    

