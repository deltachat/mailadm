import pkg_resources
import qrcode
import os
from PIL import ImageFont, ImageDraw, Image


def gen_qr(url, text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    lines = text.rstrip().split("\n")

    width = 256
    font_size = 14
    font_height = len(lines) * font_size * 2
    height = 256 + font_height
    qr_padding = 6
    text_margin_right = 6

    ttf_path = pkg_resources.resource_filename('mailadm', 'data/opensans-regular.ttf')
    logo_path = pkg_resources.resource_filename('mailadm', 'data/delta-chat-bw.png')
    assert os.path.exists(ttf_path), ttf_path

    font = ImageFont.truetype(font=ttf_path, size=font_size)

    logo_img = Image.open(logo_path)

    image = Image.new("RGBA", (width, height), "white")

    draw = ImageDraw.Draw(image)

    qr_final_size = width - (qr_padding * 2)
    logo_width = int(qr_final_size / 4)

    draw.multiline_text((text_margin_right + logo_width, height - font_height), text,
                        font=font, fill="black", align="center")

    image.paste(qr_img.resize((qr_final_size, qr_final_size), resample=Image.NEAREST),
                (qr_padding, qr_padding))

    logo = logo_img.resize((logo_width, logo_width), resample=Image.NEAREST)
    image.paste(logo, (0, qr_final_size + qr_padding), mask=logo)

    return image
