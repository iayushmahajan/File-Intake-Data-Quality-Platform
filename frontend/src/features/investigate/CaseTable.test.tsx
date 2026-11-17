import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { applicationRoutes } from "../../routes";
import fixture from "../../../scripts/fixtures/investigation.json";
import { type Evidence, type Flags, type Summary, fields } from "./contracts";
import { caseFindings } from "./CaseTable";
const evidence = fixture as unknown as Evidence;
const flags = Object.fromEntries(Object.keys(evidence.flags).map(key => [key,false])) as unknown as Flags;
const cases: Summary[] = fields.map((field,index) => ({...evidence, field, discrepancy_id:index ? `opaque-case-${index}` : evidence.discrepancy_id, candidate_count: index ? 1 : 2, flags: {...flags, confirmed_conflict: index===0, has_missing: index===1, has_unsupported:index===2}, requires_attention:index<3}));
const job = {id:7,job_kind:"raha_flights_v1",contract_version:1,status:"completed",filename_original:"records.csv",observation_count:26};
const json = (value:unknown,status=200) => new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json"}});
let custom:((url:URL)=>Promise<Response|null>|Response|null)|null;
let routers:ReturnType<typeof createMemoryRouter>[]=[];
function page(url:URL) {return {job_id:7,total:31,page:Number(url.searchParams.get("page")),page_size:15,discrepancies:cases,ungroupable_observation_count:0};}
function mount(path="/investigate?dataset=7&view=table") {const router=createMemoryRouter(applicationRoutes,{initialEntries:[path],future:{v7_relativeSplatPath:true}});routers.push(router);render(<RouterProvider router={router} future={{v7_startTransition:true}}/>);return router;}
beforeEach(()=>{
 custom=null;vi.stubGlobal("matchMedia",vi.fn(()=>({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()})));vi.stubGlobal("scrollTo",vi.fn());Element.prototype.scrollIntoView=vi.fn();
 vi.stubGlobal("fetch",vi.fn(async(input:string)=>{const url=new URL(input),r=await custom?.(url);return r??json(url.pathname.endsWith("/discrepancies")?page(url):job);}));
});
afterEach(()=>{routers.forEach(r=>r.dispose());routers=[];vi.unstubAllGlobals();Reflect.deleteProperty(Element.prototype,"scrollIntoView");});

it("shows precise field labels, overlapping findings and reports without a review column or per-row requests",async()=>{
 mount();const table=await screen.findByRole("table",{name:"Cases"});await within(table).findByText("Actual arrival time");
 for(const label of ["Scheduled departure time","Actual departure time","Scheduled arrival time","Actual arrival time"])expect(within(table).getByText(label)).toBeInTheDocument();
 for(const finding of ["Sources disagree","Missing or unavailable information","Uncertain evidence","No detected issue"])expect(within(table).getByText(finding)).toBeInTheDocument();
 expect(within(table).queryByRole("columnheader",{name:/review/i})).not.toBeInTheDocument();expect(within(table).getAllByRole("row")).toHaveLength(5);
 expect(screen.queryByRole("heading",{name:"Discrepancy queue"})).not.toBeInTheDocument();expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
 expect(vi.mocked(fetch).mock.calls).toHaveLength(2);expect(vi.mocked(fetch).mock.calls.every(([,o])=>!o?.method||o.method==="GET")).toBe(true);
});
it("keeps simultaneous conflict, missing and uncertain evidence visible without implying correctness",()=>{
 expect(caseFindings({...cases[0],flags:{...flags,confirmed_conflict:true,has_placeholders:true,internal_source_conflict:true}})).toEqual(["Sources disagree","Missing or unavailable information","Uncertain evidence"]);
 expect(caseFindings(cases[3])).toEqual(["No detected issue"]);
 expect(caseFindings({...cases[3],requires_attention:true})).toEqual(["Needs closer inspection"]);
});
it("preserves dataset, filters, page and unrelated context in stable case-ID links and browser history",async()=>{
 const router=mount("/investigate?dataset=7&view=table&kind=all&page=2&field=act_dep_time&keep=yes");const table=await screen.findByRole("table",{name:"Cases"});const link=await within(table).findByRole("link",{name:/Open case.*Actual departure/});
 const url=new URL(link.getAttribute("href")!,"http://local");expect(url.searchParams.get("discrepancy")).toBe("opaque-case-1");expect(url.searchParams.get("page")).toBe("2");expect(url.searchParams.get("field")).toBe("act_dep_time");expect(url.searchParams.get("dataset")).toBe("7");expect(url.searchParams.get("keep")).toBe("yes");
 // Invalid selected-detail fixture yields a safe error; URL history still identifies the exact selected case.
 fireEvent.click(link);await waitFor(()=>expect(router.state.location.search).toContain("discrepancy=opaque-case-1"));
 await act(async()=>{await router.navigate(-1);});await screen.findByRole("table",{name:"Cases"});expect(router.state.location.search).toContain("page=2");
 await act(async()=>{await router.navigate(1);});expect(router.state.location.search).toContain("discrepancy=opaque-case-1");
});
it("resets page for finding/field filters and uses server-side pagination",async()=>{
 const router=mount("/investigate?dataset=7&view=table&page=2");await screen.findByText("Page 2 · 31 matching cases");
 fireEvent.change(screen.getByLabelText("Finding"),{target:{value:"all"}});await screen.findByText("Page 1 · 31 matching cases");
 fireEvent.change(screen.getByLabelText("Time field"),{target:{value:"sched_arr_time"}});await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining("field=sched_arr_time"),expect.anything()));
 fireEvent.click(screen.getByRole("button",{name:"Next cases"}));await screen.findByText("Page 2 · 31 matching cases");expect(router.state.location.search).toContain("kind=all");expect(router.state.location.search).toContain("page=2");
 fireEvent.click(screen.getByRole("button",{name:"Previous cases"}));await screen.findByText("Page 1 · 31 matching cases");expect(screen.getByRole("button",{name:"Previous cases"})).toBeDisabled();
});
it("distinguishes loading and empty matching results",async()=>{
 let finish!:(r:Response)=>void;custom=url=>url.pathname.endsWith("/discrepancies")?new Promise<Response>(resolve=>{finish=resolve;}):null;
 mount();await screen.findByText("Loading cases…");expect(screen.queryByText(/No cases match/)).not.toBeInTheDocument();
 await act(async()=>finish(json({job_id:7,total:0,page:1,page_size:15,discrepancies:[],ungroupable_observation_count:0})));
 await screen.findByText(/No cases match these filters/);expect(screen.getByRole("button",{name:"Next cases"})).toBeDisabled();
});
it("shows storage/projection failures and retries without turning them into zero results",async()=>{
 let fail=true;custom=url=>url.pathname.endsWith("/discrepancies")&&fail?json({detail:"Projection unavailable."},503):null;
 mount();expect(await screen.findByRole("alert")).toHaveTextContent("Projection unavailable.");expect(screen.queryByText(/No cases match/)).not.toBeInTheDocument();fail=false;fireEvent.click(screen.getByRole("button",{name:"Retry cases"}));await screen.findByRole("table",{name:"Cases"});
});
it("rejects inconsistent row identity or unsupported fields rather than rendering misleading rows",async()=>{
 custom=url=>url.pathname.endsWith("/discrepancies")?json({...page(url),discrepancies:[cases[0],cases[0]]}):null;
 mount();expect(await screen.findByRole("alert")).toHaveTextContent("Unexpected discrepancy page");expect(screen.queryByRole("table",{name:"Cases"})).not.toBeInTheDocument();
});
