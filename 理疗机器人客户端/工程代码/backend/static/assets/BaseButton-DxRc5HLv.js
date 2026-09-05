import{I as r,o as l,c as i,r as m,n as g}from"./index-BQO8CURD.js";/**
 * @license lucide-vue-next v0.300.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */var n={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor","stroke-width":2,"stroke-linecap":"round","stroke-linejoin":"round"};/**
 * @license lucide-vue-next v0.300.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const k=e=>e.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase(),f=(e,o)=>({size:t,strokeWidth:s=2,absoluteStrokeWidth:a,color:c,class:_,...u},{attrs:b,slots:d})=>r("svg",{...n,width:t||n.width,height:t||n.height,stroke:c||n.stroke,"stroke-width":a?Number(s)*24/Number(t):s,...b,class:["lucide",`lucide-${k(e)}`],...u},[...o.map(h=>r(...h)),...d.default?[d.default()]:[]]);/**
 * @license lucide-vue-next v0.300.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const C=f("LockIcon",[["rect",{width:"18",height:"11",x:"3",y:"11",rx:"2",ry:"2",key:"1w4ew1"}],["path",{d:"M7 11V7a5 5 0 0 1 10 0v4",key:"fwvmzm"}]]),y=(e,o)=>{const t=e.__vccOpts||e;for(const[s,a]of o)t[s]=a;return t},w=["disabled"],p={key:0,class:"base-button__loading"},v={key:1,class:"base-button__content"},B={__name:"BaseButton",props:{type:{type:String,default:"primary",validator:e=>["primary","secondary","ghost"].includes(e)},size:{type:String,default:"medium",validator:e=>["small","medium","large"].includes(e)},disabled:{type:Boolean,default:!1},loading:{type:Boolean,default:!1}},emits:["click"],setup(e,{emit:o}){const t=o;function s(a){t("click",a)}return(a,c)=>(l(),i("button",{class:g(["base-button",`base-button--${e.type}`,`base-button--${e.size}`,{"is-disabled":e.disabled,"is-loading":e.loading}]),disabled:e.disabled||e.loading,onClick:s},[e.loading?(l(),i("span",p,"...")):(l(),i("span",v,[m(a.$slots,"default",{},void 0)]))],10,w))}},$=y(B,[["__scopeId","data-v-6417c567"]]);export{$ as B,C as L,y as _,f as c};
