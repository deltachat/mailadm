import pkg_resources
import qrcode
import os
from PIL import ImageFont, ImageDraw, Image


def gen_qr(config, token_info):

    info = ("{prefix}******@{domain} {expiry}\n".format(
            domain=config.sysconfig.mail_domain, prefix=token_info.prefix,
            expiry=token_info.expiry))

    steps = (
            "1. Install https://get.delta.chat\n"
            "2. Scan QR Code to get account\n"
            "3. Choose nickname, enjoy chatting\n"
            .format(
            domain=config.sysconfig.mail_domain, prefix=token_info.prefix,
            expiry=token_info.expiry, name=token_info.name))
    url = token_info.get_qr_uri()

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    num_lines = len(info) + len(steps) + 1

    size = width = 384
    font_size = 16
    font_height = font_size * num_lines
    height = size + font_height
    qr_padding = 6
    text_margin_right = 6

    ttf_path = pkg_resources.resource_filename('mailadm', 'data/opensans-regular.ttf')
    logo_bw_path = pkg_resources.resource_filename('mailadm', 'data/delta-chat-bw.png')
    logo_red_path = pkg_resources.resource_filename('mailadm', 'data/delta-chat-red.png')
    assert os.path.exists(ttf_path), ttf_path

    font = ImageFont.truetype(font=ttf_path, size=font_size)

    logo_img = Image.open(logo_bw_path)

    image = Image.new("RGBA", (width, height), "white")

    draw = ImageDraw.Draw(image)

    qr_final_size = width - (qr_padding * 2)
    logo_width = int(qr_final_size / 4)

    # draw text
    draw.multiline_text((text_margin_right + logo_width, height - font_height), steps + info,
                        font=font, fill="black", align="left")

    # paste QR code
    image.paste(qr_img.resize((qr_final_size, qr_final_size), resample=Image.NEAREST),
                (qr_padding, qr_padding))

    logo = logo_img.resize((logo_width, logo_width), resample=Image.NEAREST)
    image.paste(logo, (0, qr_final_size + qr_padding), mask=logo)

    # red background delta logo
    logo2_img = Image.open(logo_red_path)
    logo2_width = int(size / 6)
    logo2 = logo2_img.resize((logo2_width, logo2_width), resample=Image.NEAREST)
    pos = int((size / 2) - (logo2_width / 2))
    image.paste(logo2, (pos, pos), mask=logo2)

    return image
