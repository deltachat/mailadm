import qrcode
from PIL import ImageFont, ImageDraw, Image

def makeqr(url, duration, server):
    # generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img.save("qr.png")

    font_height = 44
    width = 256
    height = 256 + font_height
    qr_padding = 6
    text_margin_right = 10

    font = ImageFont.truetype(font="OpenSans/OpenSans-Regular.ttf", size=12)

    image = Image.new("RGB", (width, height), "white")

    draw = ImageDraw.Draw(image)

    text = "Scan this Qr-Code to get an Burneraccount\n" + \
        "on " + server + " that expires in " + duration

    draw.multiline_text((text_margin_right, height - font_height), text,
                        font=font, fill="black", align="center")

    qr_final_size = width-(qr_padding*2)

    image.paste(qr_img.resize((qr_final_size, qr_final_size), resample=Image.NEAREST),
                (qr_padding, qr_padding))

    image.save("burner-" + server + "_" +
               duration.replace(" ", "_") + ".png")

