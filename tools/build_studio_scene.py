"""Reconstruct the approved imagegen concept with editable Blender geometry."""
import bpy, math, random
from pathlib import Path
from mathutils import Vector
random.seed(19)
root=Path(__file__).resolve().parents[1]
out=root/'outputs/studio-v2';assets=root/'web/scene-assets/study-v2'
out.mkdir(parents=True,exist_ok=True);assets.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=24
s.cycles.use_denoising=True
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.film_transparent=True
s.world.color=(.12,.14,.2)
s.view_settings.view_transform='AgX'
fore=[]; lights=[]
def material(name,col,metal=0,emit=0,wood=False):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
 n=m.node_tree.nodes;p=n.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1)
 p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.4 if metal else .65
 if emit:p.inputs['Emission Color'].default_value=(*col,1);p.inputs['Emission Strength'].default_value=emit
 if wood:
  tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=4;tex.inputs['Detail'].default_value=3
  coords=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY';mapping.inputs[1].default_value=(2,32,4)
  ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.035,.014,.008,1);ramp.color_ramp.elements[1].color=(*col,1)
  link=m.node_tree.links;link.new(coords.outputs['Generated'],mapping.inputs[0]);link.new(mapping.outputs[0],tex.inputs['Vector']);link.new(tex.outputs['Fac'],ramp.inputs[0]);link.new(ramp.outputs[0],p.inputs['Base Color'])
 return m
navy=material('Midnight blue plaster',(.095,.145,.22));trim=material('Blue trim',(.13,.2,.29));walnut=material('Walnut grain',(.26,.115,.055),wood=True)
gold=material('Brushed brass',(.58,.35,.12),.72);cream=material('Warm ivory',(.78,.65,.45));sky=material('Night sky',(.012,.035,.095),emit=.35)
glow=material('Amber glow',(.95,.54,.18),emit=3);moon=material('Moon',(.48,.68,1),emit=2)
leaf=material('Leaves',(.08,.22,.13));blue=material('Ceramic whale',(.25,.48,.6));rain=material('Rain highlights',(.15,.3,.48),emit=.3)
def finish(o,name,m,fg=False):
 o.name=name;o.data.materials.append(m)
 if fg:fore.append(o)
 return o
def cube(name,pos,size,m,fg=False,bevel=.025):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:mod=o.modifiers.new('Rounded edges','BEVEL');mod.width=bevel;mod.segments=4;o.modifiers.new('Normals','WEIGHTED_NORMAL')
 return finish(o,name,m,fg)
def ball(name,pos,size,m,fg=False):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=pos);o=bpy.context.object;o.scale=size
 for p in o.data.polygons:p.use_smooth=True
 return finish(o,name,m,fg)
def tube(name,points,r,m,fg=False):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3
 sp=c.splines.new('POLY');sp.points.add(len(points)-1)
 for p,co in zip(sp.points,points):p.co=(*co,1)
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);return finish(o,name,m,fg)
def arch(name,cx,y,zbase,r,straight,m,radius=.035):
 pts=[(cx-r,y,zbase),(cx-r,y,zbase+straight)]
 pts += [(cx+r*math.cos(t),y,zbase+straight+r*math.sin(t)) for t in [math.pi-i*math.pi/48 for i in range(49)]]
 pts += [(cx+r,y,zbase)]
 return tube(name,pts,radius,m)
def light(name,pos,power,col,size=2,target=(0,0,2)):
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.color=col;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();lights.append(o);return o
cube('Room back',(0,2.5,2.7),(12,.2,7),navy)
cube('Window night',(-3.65,2.35,3.2),(2.6,.08,4.8),sky)
arch('Window arch',-3.65,2.22,.9,1.3,3.15,walnut,.075)
for x in [-4.3,-3.65,-3.0]:cube('Window mullion',(x,2.2,2.9),(.035,.09,3.8),walnut)
for z in [1.0,2.15,3.25,4.25]:cube('Window crossbar',(-3.65,2.18,z),(2.55,.1,.045),walnut)
ball('Moon',(-3.85,2.24,4.25),(.22,.025,.22),moon)
for i in range(25):
 x=random.uniform(-4.83,-2.43);h=random.uniform(.13,.5)
 cube('City silhouette',(x,2.27,1.1+h/2),(.09,.02,h),trim,bevel=0)
 for j in range(3):
  if random.random()>.4:cube('City lights',(x,2.24,1.13+j*.09),(.025,.012,.022),glow,bevel=0)
for i in range(90):
 x=random.uniform(-4.85,-2.4);z=random.uniform(1.15,4.85)
 tube('Rain on glass',[(x,2.15,z),(x+.008,2.15,z-random.uniform(.03,.14))],.003,rain)
# Pleated curtains with actual wave mesh.
cloth=material('Dusty blue linen',(.18,.26,.4))
for center in [-5.05,-2.18]:
 verts=[];faces=[];nx=50;nz=20
 for j in range(nz+1):
  z=.8+j*4.8/nz
  for i in range(nx+1):
   x=center+(i/nx-.5)*.6+.08*math.sin(j/nz*math.pi)
   verts.append((x,1.92+.075*math.cos(i/nx*math.pi*10),z))
 for j in range(nz):
  for i in range(nx):
   a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
 mesh=bpy.data.meshes.new('Curtain');mesh.from_pydata(verts,[],faces);o=bpy.data.objects.new('Pleated curtain',mesh);bpy.context.collection.objects.link(o);finish(o,'Pleated curtain',cloth)
 for p in mesh.polygons:p.use_smooth=True
arch('Central inset',0,2.34,1.05,1.8,2.55,trim,.055);arch('Fine brass arch',0,2.27,1.05,1.73,2.55,gold,.009)
for x in [-1.95,1.95]:cube('Wall pilaster',(x,2.3,2.9),(.06,.06,5.5),trim)
cube('Dado rail',(0,2.28,1.15),(10,.1,.09),trim)
for x in [-1.4,-.7,0,.7,1.4]:
 for dx in [-.29,.29]:cube('Panel stile',(x+dx,2.3,.55),(.025,.05,.9),trim)
# right bookcase
cube('Bookcase back',(3.65,2.15,2.8),(2.9,.2,5.8),walnut)
for x in [2.2,5.1]:cube('Bookcase side',(x,1.85,2.9),(.12,.8,5.6),walnut)
for z in [.8,1.9,3,4.1,5.2]:
 cube('Shelf',(3.65,1.82,z),(2.95,.85,.11),walnut)
 cube('Shelf strip',(3.65,1.93,z-.075),(2.65,.03,.018),glow)
for shelf in [1.9,3,4.1]:
 for i in range(7):
  col=random.choice([(.18,.25,.34),(.34,.37,.4),(.42,.31,.22),(.21,.31,.31)])
  x=2.48+i*.19;h=random.uniform(.5,.75)
  cube('Book',(x,1.72,shelf+.06+h/2),(.16,.34,h),material('Book cloth',col))
  for z in [shelf+.16,shelf+h-.05]:cube('Book foil',(x,1.54,z),(.1,.009,.014),gold,bevel=.002)
ball('Whale body',(4.22,1.6,3.36),(.35,.15,.18),blue)
tube('Whale tail',[(4.45,1.6,3.4),(4.63,1.6,3.5),(4.7,1.6,3.7)],.045,blue)
ball('Whale fluke',(4.68,1.6,3.68),(.15,.06,.055),blue)
ball('Whale eye',(3.98,1.455,3.4),(.018,.012,.018),navy)
cube('Plant pot',(4.7,1.65,5.45),(.35,.35,.4),cream)
for j in range(3):
 pts=[(4.6+j*.15,1.35,5.6-i*.18) for i in range(14)]
 tube('Vine',pts,.012,leaf)
 for i,p in enumerate(pts):
  o=ball('Leaf',(p[0]+(.1 if i%2 else -.1),p[1]-.02,p[2]),(.13,.025,.065),leaf);o.rotation_euler.y=(-.6 if i%2 else .6)
for x in [-2.0,2.0]:
 cube('Sconce bracket',(x,2.1,3.25),(.06,.25,.55),gold)
 ball('Sconce',(x,1.95,3.45),(.095,.095,.24),glow)
 light('Sconce light',(x,1.7,3.4),35,(1,.62,.3),.7,(x,2.5,3.4))
# foreground full desk with cream edge and brass line
cube('Desk apron',(0,-.6,.15),(11,1.25,1.35),walnut,True,.06)
cube('Cream desk edge',(0,-.65,.88),(11,1.6,.16),cream,True,.075)
cube('Walnut desktop',(0,-.63,.985),(10.95,1.55,.075),walnut,True,.04)
cube('Brass inlay',(0,-1.455,.89),(10.7,.015,.015),gold,True,.004)
for x in [-3.8,-1.3,1.3,3.8]:
 cube('Front panel trim',(x,-1.24,.2),(.025,.025,.9),gold,True,.003)
cube('Notebook',(-3.6,-.6,1.065),(1,.55,.09),trim,True,.025)
cube('Pages',(-3.6,-.61,1.08),(.94,.53,.05),cream,True,.01)
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.17,depth=.25,location=(-2.75,-.6,1.17));finish(bpy.context.object,'Cup',cream,True)
tube('Cup handle',[(-2.57,-.6,1.27),(-2.42,-.6,1.24),(-2.42,-.6,1.09),(-2.57,-.6,1.08)],.025,cream,True)
# Mushroom lamp lathed dome
bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=.18,radius2=.12,depth=.7,location=(3.65,-.55,1.42));finish(bpy.context.object,'Lamp stem',cream,True)
ball('Lamp dome',(3.65,-.55,1.86),(.52,.52,.3),cream,True)
ball('Lamp base',(3.65,-.55,1.05),(.25,.25,.045),gold,True)
key=light('Front softbox',(-1,-4,4.5),600,(.75,.84,1),6)
lamp=light('Desk lamp',(3.65,-.55,1.65),55,(1,.62,.25),.7,(3.65,-.55,.9))
light('Window fill',(-3,0,4),180,(.27,.47,1),3)
bpy.ops.object.camera_add(location=(0,-14,3.45));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1,2.9))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=10.4;s.camera=cam
objects=[o for o in s.objects if o.type in ['MESH','CURVE']]
for theme,color in [('warm',(.92,.85,.74)),('cool',(.56,.72,1))]:
 key.data.color=color
 for layer in ['background','foreground']:
  for o in objects:o.hide_render=(o in fore) if layer=='background' else (o not in fore)
  s.render.filepath=str(assets/f'{theme}-{layer}.png');bpy.ops.render.render(write_still=True)
for o in objects:o.hide_render=False
key.data.color=(.92,.85,.74)
s.render.filepath=str(out/'blender-room.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'rain-study.blend'))
print('STUDIO_RENDER_COMPLETE')
