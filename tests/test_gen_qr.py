from mailadm.gen_qr import gen_qr
from pyzbar.pyzbar import decode


def test_gen_qr(db):
    with db.write_transaction() as conn:
        config = conn.config
        token = conn.add_token("burner1", expiry="1w", token="1w_7wDioPeeXyZx96v3", prefix="pp")

    image = gen_qr(config=config, token_info=token)
    qr_decoded = decode(image)[0]
    assert token.token in str(qr_decoded.data)
