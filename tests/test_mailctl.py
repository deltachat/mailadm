from pathlib import Path
from mailadm.mailctl import MailController
from mailadm.config import Config


def test_gen_sysfiles(make_ini_from_values):
    inipath = make_ini_from_values(
        name="burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")
    config = Config(inipath)
    with config.write_transaction() as conn:
        tc = conn.get_tokenconfig_by_name("burner1")

        NUM_USERS = 50
        users = []
        for i in range(NUM_USERS):
            users.append(conn.add_email_account(tc))

        mc = MailController(config)
        mc.gen_sysfiles(conn)

    # check dovecot user db was generated
    p = Path(config.sysconfig.path_dovecot_users)
    data = p.read_text()
    for user in users:
        assert user.addr in data and user.hash_pw in data

    # check postfix virtual mailboxes was generated
    p = Path(config.sysconfig.path_virtual_mailboxes)
    data = p.read_text()
    for user in users:
        assert user.addr in data
