import sys, numpy as np, onnxruntime as o
from PIL import Image
S=o.InferenceSession(sys.argv[1])
def seg(img):  # img float HxWx3 0..1
    h,w=img.shape[:2]
    x=np.asarray(Image.fromarray((img*255).astype(np.uint8)).resize((1024,1024),Image.BILINEAR)).astype(np.float32)/255-0.5
    m=S.run(['output'],{'input':x.transpose(2,0,1)[None]})[0][0,0]
    m=(m-m.min())/(m.max()-m.min()+1e-6)
    return np.asarray(Image.fromarray((m*255).astype(np.uint8)).resize((w,h),Image.BILINEAR)).astype(np.float32)/255
UP='/root/.claude/uploads/d9dcdad8-7f30-502a-b696-86e81cf9eb36/'
L=lambda n: np.asarray(Image.open(UP+n).convert('RGB')).astype(np.float32)/255
jobs={ # name: (file, crop x0,y0,x1,y1)
 'gate_full':('819905a1-image.png',None),
 'gate_wolf':('819905a1-image.png',(380,0,1000,864)),
 'cart_full':('e90b9966-image.png',None),
 'cart_man':('e90b9966-image.png',(300,200,1150,830)),
 'cart_guard':('e90b9966-image.png',(60,100,460,480)),
 'forest_man':('36ead0f1-image.png',(40,220,520,853)),
 'forest_full':('36ead0f1-image.png',None),
 'beast':('bb93b0cd-image.jpg',(0,70,705,560)),
 'leap':('bb93b0cd-image.jpg',(780,620,1070,810)),
}
only=sys.argv[2:]
for k,(f,c) in jobs.items():
    if only and k not in only: continue
    im=L(f); full=np.zeros(im.shape[:2],np.float32)
    if c: x0,y0,x1,y1=c; full[y0:y1,x0:x1]=seg(im[y0:y1,x0:x1])
    else: full=seg(im)
    Image.fromarray((full*255).astype(np.uint8)).save(f'masks/{k}.png')
    print(k, full.mean())
