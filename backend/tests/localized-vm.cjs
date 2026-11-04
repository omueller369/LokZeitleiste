/* VM fixtures load the same deterministic source-key resolver as browser pages. */
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const bundle=fs.readFileSync(path.join(__dirname,'../lokzeitleiste/static/messages.js'),'utf8');
function prepare(context){if(!context.CtlText)vm.runInContext(bundle,context);return context;}
module.exports={...vm,
 runInNewContext(code,context={},options){vm.createContext(context);prepare(context);return vm.runInContext(code,context,options);},
 runInContext(code,context,options){prepare(context);return vm.runInContext(code,context,options);},
 resolveHtml(value){const ctx=vm.createContext({});prepare(ctx);return ctx.CtlText.restore(value);}
};
