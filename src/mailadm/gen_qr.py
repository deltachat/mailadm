import pkg_resources
import qrcode
import os
from PIL import ImageFont, ImageDraw, Image


def gen_qr(config, token_info):

    info = ("{prefix}******@{domain} {expiry}\n".format(
            domain=config.mail_domain, prefix=token_info.prefix,
            expiry=token_info.expiry))

    steps = ("1. Install https://get.delta.chat\n"
            "2. From setup screen scan above QR code\n"
            "3. Choose nickname & avatar\n"
            "+ chat with any e-mail address ...\n")

    # load QR code
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

    # paint all elements
    ttf_path = pkg_resources.resource_filename('mailadm', 'data/opensans-regular.ttf')
    logo_red_path = pkg_resources.resource_filename('mailadm', 'data/delta-chat-red.png')

    assert os.path.exists(ttf_path), ttf_path
    font_size = 16
    font = ImageFont.truetype(font=ttf_path, size=font_size)

    num_lines = (info + steps).count("\n") + 2

    size = width = 384
    qr_padding = 6
    text_margin_right = 12
    text_height = font_size * num_lines
    height = size + text_height + qr_padding * 2

    image = Image.new("RGBA", (width, height), "white")

    draw = ImageDraw.Draw(image)

    qr_final_size = width - (qr_padding * 2)

    # draw text
    info_pos = (width - font.getsize(info.strip())[0]) // 2
    draw.multiline_text((info_pos, size - qr_padding // 2), info,
                        font=font, fill="red", align="right")
    draw.multiline_text((text_margin_right, height - text_height + font_size * 1.0), steps,
                        font=font, fill="black", align="left")

    # paste QR code
    image.paste(qr_img.resize((qr_final_size, qr_final_size), resample=Image.NEAREST),
               (qr_padding, qr_padding))

    # paste black and white logo
    # logo_bw_path = pkg_resources.resource_filename('mailadm', 'data/delta-chat-bw.png')
    # logo_img = Image.open(logo_bw_path)
    # logo = logo_img.resize((logo_width, logo_width), resample=Image.NEAREST)
    # image.paste(logo, (0, qr_final_size + qr_padding), mask=logo)

    # red background delta logo
    logo2_img = Image.open(logo_red_path)
    logo2_width = int(size / 6)
    logo2 = logo2_img.resize((logo2_width, logo2_width), resample=Image.NEAREST)
    pos = int((size / 2) - (logo2_width / 2))
    image.paste(logo2, (pos, pos), mask=logo2)

    return image
