import pathlib,json
from PIL import Image,ImageDraw
r=pathlib.Path(__file__).resolve().parent
p=[[0,580],[80,515],[180,490],[280,515],[350,565],[405,603],[450,625],[530,598],[650,560],[780,525],[855,508],[870,548],[920,570],[1000,580],[1080,563],[1100,510],[1180,500],[1350,515],[1520,534],[1615,545],[1710,510],[1810,455],[1920,430],[1920,1080],[230,1080],[255,970],[275,915],[200,915],[100,930],[0,920]]
im=Image.open(r.parent/'input/S05.png').convert('RGB')
m=Image.new('L',im.size);ImageDraw.Draw(m).polygon([tuple(x) for x in p],fill=255);m.save(r/'person_mask.png')
color=Image.new('RGB',im.size,(0,210,110));blend=Image.blend(im,color,.3)
im.paste(blend,mask=m);im.save(r/'mask_preview.jpg',quality=94)
(r/'mask_provenance.json').write_text(json.dumps(dict(source='assistant hand-traced original image, no model outline used',type='approximate visible person, includes hair and clothing, excludes foreground contact head',polygon=p,not_ground_truth=True,limitations='draft boundary; not a bare-back mask; prior contour references overlap this mask and are not independent evaluation'),indent=2)+'\n','utf-8')
