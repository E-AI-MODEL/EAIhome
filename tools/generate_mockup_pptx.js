/** Two editable fictional slides, built with PptxGenJS. */
const pptxgen = require('pptxgenjs');
let check = null;
try { check = require('/home/oai/skills/slides/pptxgenjs_helpers'); }
catch (_) { /* External CI runner uses the ordinary PptxGenJS package. */ }
const p = new pptxgen();
p.layout = 'LAYOUT_WIDE';
p.author = 'EAIhome testdata';
p.title = 'EAIhome | Fictief project Atlas';
p.lang = 'nl-NL';
p.theme = {headFontFace:'Aptos Display',bodyFontFace:'Aptos',lang:'nl-NL'};
const C = {bg:'F4F7FB',dark:'1B334A',blue:'245F9E',muted:'5E7288',white:'FFFFFF',edge:'D0DAE4'};
function validate(s) {
  if (check) {
    check.warnIfSlideHasOverlaps(s,p);
    check.warnIfSlideElementsOutOfBounds(s,p);
  }
}
{
  const s=p.addSlide(); s.background={color:C.bg};
  s.addText('EAIhome',{x:.8,y:.72,w:11.4,h:.7,fontSize:38,bold:true,color:C.dark,margin:0});
  s.addText('Project Atlas | FICTIEVE TESTPRESENTATIE',{x:.8,y:1.62,w:11.4,h:.38,fontSize:15,bold:true,color:C.muted,margin:0});
  s.addShape(p.ShapeType.roundRect,{x:.8,y:2.8,w:11.7,h:2.5,rectRadius:.15,fill:{color:C.white},line:{color:C.edge,width:1}});
  s.addText('EAIHOME-DEMO-001',{x:1.22,y:3.3,w:10.3,h:.5,fontSize:27,bold:true,color:C.blue,margin:0});
  s.addText('20 november 2026: controleoverleg\nACT-001: controleer agenda en stukken',{x:1.22,y:4.04,w:10.3,h:.85,fontSize:18,color:C.dark,margin:0});
  validate(s);
}
{
  const s=p.addSlide(); s.background={color:C.bg};
  s.addText('Open taak en besluit',{x:.8,y:.7,w:11.8,h:.6,fontSize:29,bold:true,color:C.dark,margin:0});
  [['ACT-001','Open','Controleer agenda en stukken'],['ACT-002','Afgerond','Verzamel opmerkingen'],['Besluit','Voorgesteld','Nog niet goedgekeurd']].forEach((a,i)=>{
    const x=.8+i*4.2;
    s.addShape(p.ShapeType.roundRect,{x:x,y:2.2,w:3.75,h:2.7,rectRadius:.15,fill:{color:C.white},line:{color:C.edge,width:1}});
    s.addText(a[0],{x:x+.25,y:2.65,w:3.2,h:.35,fontSize:22,bold:true,color:C.blue,margin:0});
    s.addText(a[1],{x:x+.25,y:3.22,w:3.2,h:.34,fontSize:16,bold:true,color:C.dark,margin:0});
    s.addText(a[2],{x:x+.25,y:3.85,w:3.2,h:.65,fontSize:15,color:C.muted,margin:0});
  });
  s.addText('Fictieve gegevens. Geen externe actie toegestaan.',{x:.8,y:6.65,w:11.5,h:.3,fontSize:12,color:C.muted,margin:0});
  validate(s);
}
p.writeFile({fileName:process.argv[2]}).catch(err=>{console.error(err);process.exit(1)});
