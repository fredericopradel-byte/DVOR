// Page geometry is used only to associate topology. Never converts pixels into NM.
const multiply=(a,b)=>[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export function curvedPaths(extraction){
  const viewport=extraction.pageTransform||[1,0,0,-1,0,extraction.height],out=[];
  let samples=0;const limited=()=>Object.assign([],{limited:true});
  let state={matrix:[1,0,0,1,0,0],dash:[]},stack=[],paths=[];
  for(const op of extraction.vectors||[]){
    if(op.operator==='save')stack.push(structuredClone(state));
    else if(op.operator==='restore')state=stack.pop()||{matrix:[1,0,0,1,0,0],dash:[]};
    else if(op.operator==='transform')state.matrix=multiply(state.matrix,op.args);
    else if(op.operator==='setDash')state.dash=op.args?.[0]||[];
    else if(op.operator==='constructPath'){
      if(op.args?.[0]?.length>25000||op.args?.[1]?.length>50000)return limited();
      paths=[];const matrix=multiply(viewport,state.matrix),point=(x,y)=>({x:matrix[0]*x+matrix[2]*y+matrix[4],y:matrix[1]*x+matrix[3]*y+matrix[5]});
      let i=0,at=null,path=null;const coords=op.args[1];
      for(const code of op.args[0]){
        if(code===13){at=point(coords[i++],coords[i++]);path={points:[at],curved:false,closed:false,evidenceIds:['vector-'+op.index]};paths.push(path);}
        else if(code===14){at=point(coords[i++],coords[i++]);path?.points.push(at);}
        else if([15,16,17].includes(code)){
          if(!at||!path){paths=[];break;}
          const a=at,b=code===16?at:point(coords[i++],coords[i++]),c=point(coords[i++],coords[i++]),d=code===17?c:point(coords[i++],coords[i++]);
          if((samples+=16)>200000||path.points.length>4096)return limited();
          for(let k=1;k<=16;k++){const t=k/16,u=1-t;path.points.push({x:u**3*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t**3*d.x,y:u**3*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t**3*d.y});}
          at=d;path.curved=true;
        }else if(code===18){if(path){path.closed=true;at=path.points[0];}}
        else if(code===19){i+=4;path=null;at=null;}
        else{paths=[];break;}
      }
    }else if(['stroke','closeStroke','fillStroke','eoFillStroke','closeFillStroke','closeEOFillStroke'].includes(op.operator)){
      for(const path of paths)if(op.operator==='stroke'&&path.curved&&!path.closed&&distance(path.points[0],path.points.at(-1))>1e-6)out.push({...path,dashed:state.dash.some(v=>v>0),evidenceIds:[...path.evidenceIds,'vector-'+op.index]});
      paths=[];
    }else if(['endPath','fill','eoFill'].includes(op.operator))paths=[];
  }return out;
}
// Least-squares circle in page units, for topological association only.
export function circularPath(path){
  const pts=path.points;if(pts.length<8)return null;
  const origin=pts[0],p=pts.map(a=>({x:a.x-origin.x,y:a.y-origin.y})),n=p.length;
  const sum=fn=>p.reduce((s,a)=>s+fn(a),0),sxx=sum(a=>a.x*a.x),syy=sum(a=>a.y*a.y),sxy=sum(a=>a.x*a.y),sx=sum(a=>a.x),sy=sum(a=>a.y);
  const m=[[sxx,sxy,sx,sum(a=>-a.x*(a.x*a.x+a.y*a.y))],[sxy,syy,sy,sum(a=>-a.y*(a.x*a.x+a.y*a.y))],[sx,sy,n,-sxx-syy]];
  for(let i=0;i<3;i++){let pivot=i;for(let j=i+1;j<3;j++)if(Math.abs(m[j][i])>Math.abs(m[pivot][i]))pivot=j;if(Math.abs(m[pivot][i])<1e-9)return null;[m[i],m[pivot]]=[m[pivot],m[i]];const d=m[i][i];for(let k=i;k<4;k++)m[i][k]/=d;for(let j=0;j<3;j++)if(j!==i){const d=m[j][i];for(let k=i;k<4;k++)m[j][k]-=d*m[i][k];}}
  const center={x:origin.x-m[0][3]/2,y:origin.y-m[1][3]/2},radii=pts.map(a=>distance(a,center)),radius=radii.reduce((a,b)=>a+b,0)/n;
  if(!Number.isFinite(radius)||radius<=0||Math.max(...radii.map(r=>Math.abs(r-radius)))>radius*.015)return null;
  let sweep=0,sign=0;
  for(let i=1;i<n;i++){const a=Math.atan2(pts[i-1].y-center.y,pts[i-1].x-center.x),b=Math.atan2(pts[i].y-center.y,pts[i].x-center.x),delta=Math.atan2(Math.sin(b-a),Math.cos(b-a));if(Math.abs(delta)<1e-8)continue;if(sign&&Math.sign(delta)!==sign)return null;sign=Math.sign(delta);sweep+=delta;}
  if(Math.abs(sweep)<Math.PI/60||Math.abs(sweep)>Math.PI*1.9)return null;
  return {...path,center,radius,sweepDegrees:sweep*180/Math.PI};
}
