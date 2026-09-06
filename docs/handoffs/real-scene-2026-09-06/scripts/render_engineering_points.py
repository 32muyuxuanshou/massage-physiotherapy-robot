import json,pathlib
from PIL import Image,ImageDraw
root=pathlib.Path(__file__).resolve().parent
data=json.loads((root/'engineering_projection/projection.json').read_text('utf-8'))
image=Image.open(root/'input/S01.png').convert('RGB');draw=ImageDraw.Draw(image)
for p in data['points']:
    if p['inside_image']:
        x,y=p['xy_original'];draw.ellipse((x-5,y-5,x+5,y+5),fill=(255,180,0),outline=(0,0,0),width=2)
        draw.text((x+7,y-12),p['point_id'],fill=(255,230,0),stroke_width=2,stroke_fill=(0,0,0))
draw.rectangle((0,0,image.width,55),fill=(20,20,20))
draw.text((15,18),'ENGINEERING POINTS ONLY | unvalidated mapping | NOT acupoints / training labels',fill='white')
image.save(root/'engineering_projection/S01_engineering_points.png')
