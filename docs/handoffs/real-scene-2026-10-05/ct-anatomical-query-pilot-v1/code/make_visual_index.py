"""Every-case visual listing and compact pages; no score selection."""
import json
from PIL import Image, ImageDraw
from prepare_pilot import OUT, write

rows=[r for r in json.loads((OUT/'CASE_MANIFEST.json').read_text()) if r['eligible']]
records=[];lines=['# 全部来源的模型预测图','', '红：CT椎骨代理目标；白：当前方法全部初始化预测。不是穴位精度。','']
for role in ['train','dev','test','author_val_supporting']:
    cohort=[r for r in rows if r['role']==role]
    lines+=['## '+role,'']
    folder=OUT/'montages'/role;folder.mkdir(parents=True,exist_ok=True)
    for start in range(0,len(cohort),4):
        page=Image.new('RGB',(1600,1660),'white');draw=ImageDraw.Draw(page);draw.text((15,10),role+' | every qualified case; all seeds',(0,0,0))
        for j,r in enumerate(cohort[start:start+4]):
            im=Image.open(OUT/'figures'/(r['subject']+'.png'));im.thumbnail((1560,395));page.paste(im,(20,45+400*j))
        page.save(folder/(f'page_{start//4+1:02}.jpg'),quality=92)
    for r in cohort:
        path=OUT/'figures'/(r['subject']+'.png');assert path.exists()
        records.append(dict(case_id=r['subject'],role=role,path=str(path)))
        lines.append('- ['+r['subject']+'](figures/'+r['subject']+'.png)')
    lines.append('')
(OUT/'VISUAL_INDEX.md').write_text('\n'.join(lines),encoding='utf-8')
write(OUT/'VISUALIZATION_MANIFEST.json',dict(cases=len(rows),figures=len(records),all_cases_present=True,records=records))
print('ALL_CASE_VISUALS',len(records),flush=True)
