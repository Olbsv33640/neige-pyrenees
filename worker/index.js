const ORIGIN = "https://olbsv33640.github.io";
const OWNER = "Olbsv33640";
const REPO = "neige-pyrenees";
const WORKFLOW = "actualisation.yml";
const API = "https://api.github.com";
const COALESCE_MINUTES = 10;
function response(body,status,origin){return new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json; charset=utf-8","access-control-allow-origin":origin,"access-control-allow-methods":"POST, OPTIONS","access-control-allow-headers":"content-type","access-control-max-age":"86400","cache-control":"no-store","vary":"Origin"}})}
async function github(path,token,init={}){return fetch(`${API}${path}`,{...init,headers:{authorization:`Bearer ${token}`,accept:"application/vnd.github+json","x-github-api-version":"2022-11-28","content-type":"application/json",...init.headers}})}
export default {async fetch(request,env){
 const origin=request.headers.get("Origin")||"";
 if(origin!==ORIGIN)return new Response("Forbidden",{status:403});
 if(request.method==="OPTIONS")return new Response(null,{status:204,headers:{"access-control-allow-origin":origin,"access-control-allow-methods":"POST, OPTIONS","access-control-allow-headers":"content-type","access-control-max-age":"86400","vary":"Origin"}});
 if(request.method!=="POST")return response({error:"Method not allowed"},405,origin);
 if(!env.GITHUB_TOKEN)return response({error:"Worker is not configured"},503,origin);
 const workflowPath=`/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}`;
 const latest=await github(`${workflowPath}/runs?per_page=1`,env.GITHUB_TOKEN);
 if(!latest.ok)return response({error:"Could not check the latest update"},502,origin);
 const run=((await latest.json()).workflow_runs||[])[0];
 if(run){const ageMs=Date.now()-Date.parse(run.created_at),running=run.status!=="completed",cooldown=run.conclusion==="success"?COALESCE_MINUTES:2;
  if(running||ageMs<cooldown*60_000)return response({status:"already-running-or-recent",run_url:run.html_url,run_status:run.status,conclusion:run.conclusion,created_at:run.created_at},200,origin)}
 const dispatch=await github(`${workflowPath}/dispatches`,env.GITHUB_TOKEN,{method:"POST",body:JSON.stringify({ref:"main"})});
 if(dispatch.status!==204)return response({error:"GitHub did not start the update"},502,origin);
 return response({status:"queued"},202,origin);
}};
