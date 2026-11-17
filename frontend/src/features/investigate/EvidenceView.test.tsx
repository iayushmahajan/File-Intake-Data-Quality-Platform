import {useRef, useState} from "react";
import {Dialog} from "../../components/ui/dialog";
import {type CaseDetailSelection} from "./CaseDetailWindow";
import {fireEvent, render, screen, within} from "@testing-library/react";
import {expect, it} from "vitest";
import fixture from "../../../scripts/fixtures/investigation.json";
import {type Evidence} from "./contracts";
import {EvidenceView} from "./EvidenceView";
const evidence = fixture as unknown as Evidence;
function Harness({value}: {value: Evidence}) {const [detail,setDetail] = useState<CaseDetailSelection | null>(null);const returnFocus=useRef<HTMLElement>(null);return <Dialog open={!!detail} onOpenChange={open=>!open&&setDetail(null)}><div className="focused-case"><EvidenceView evidence={value} detail={detail} openDetail={setDetail} returnFocus={returnFocus} /></div></Dialog>;}
function mount(value = evidence) {return render(<Harness value={value} />);}
function records() {fireEvent.click(screen.getByRole("button", {name: /View source records/}));}

it("expands one source entry at a time with complete interpretation, identities and limitations", () => {
  mount(); records();
  const first = screen.getByRole("button", {name: `Show details for source record ${evidence.claims[0].tuple_id}`});
  expect(first).toHaveAttribute("aria-expanded", "false"); fireEvent.click(first);
  expect(first).toHaveAttribute("aria-expanded", "true");
  const row = first.closest("tr")!;
  expect(row).toHaveAttribute("data-expanded", "true");
  const claim = evidence.claims[0];
  expect(row.textContent).toContain(claim.normalization.raw);
  expect(row.textContent).toContain(claim.normalization.canonical_clock!);
  expect(row.textContent).toContain(`Observation: ${claim.tuple_id}`);
  expect(row.textContent).toContain(`Record ${claim.row_number}`);
  for (const id of first.getAttribute("aria-controls")!.split(" ")) expect(document.getElementById(id)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", {name: `Show details for source record ${evidence.claims[1].tuple_id}`}));
  expect(row).toHaveAttribute("data-expanded", "false");
  expect(document.querySelectorAll('tr[data-expanded="true"]')).toHaveLength(1);
});

it("preserves unusual raw text, identity issues and unsupported interpretations without rendering HTML", () => {
  const value = structuredClone(evidence); const claim = value.claims[0];
  claim.src = "a-very-long-source-".repeat(30); claim.normalization.raw = '  <img src=x onerror=alert(1)>\n"quoted", value  ';
  claim.normalization.status = "unsupported"; claim.normalization.canonical_clock = null;
  claim.normalization.reason = "Unsupported annotation"; claim.normalization.qualifiers = ["context retained"];
  claim.identity_issues = [{code: "source_issue", field: "src", message: "Source identity needs attention"}];
  mount(value); records(); fireEvent.click(screen.getByRole("button", {name: `Show details for source record ${claim.tuple_id}`}));
  const row = screen.getByRole("button", {name: `Hide details for source record ${claim.tuple_id}`}).closest("tr")!;
  expect(row.querySelector("pre")!.textContent).toBe(claim.normalization.raw);
  expect(row.textContent).toContain(claim.src); expect(row.textContent).toContain("Could not interpret");
  expect(row.textContent).toContain("Unsupported annotation"); expect(row.textContent).toContain("context retained"); expect(row.textContent).toContain("Source identity needs attention");
  expect(row.querySelector("img")).toBeNull();
});

it("keeps missing, unavailable and uncertain reports distinct", () => {
  mount(); records();
  for (const [status, label] of [["missing", "Empty"], ["placeholder", "Unavailable"], ["ambiguous", "Uncertain interpretation"]]) {
    const claim = evidence.claims.find(c => c.normalization.status === status)!;
    const button = screen.getByRole("button", {name: `Show details for source record ${claim.tuple_id}`}); fireEvent.click(button);
    const row = button.closest("tr")!; expect(within(row).getByText(label)).toBeInTheDocument(); expect(row.textContent).toContain(claim.normalization.raw || "∅");
    expect(within(row).getByText(status)).toBeInTheDocument();
  }
});

it("pages all bounded field claims and resets expansion, with correct empty and last-page counts", () => {
  const claims = Array.from({length: 21}, (_, i) => ({...evidence.claims[0], tuple_id: `page-record-${i}`, normalization: {...evidence.claims[0].normalization, raw: `exact ${i}`}}));
  const {unmount} = mount({...evidence, claims}); records(); fireEvent.click(screen.getByRole("button", {name: "Show details for source record page-record-0"}));
  fireEvent.click(screen.getByRole("button", {name: "Next source records"})); expect(screen.getByText("Records 11–20 of 21")).toBeInTheDocument(); expect(document.querySelectorAll('tr[data-expanded="true"]')).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", {name: "Next source records"})); expect(screen.getByText("Records 21–21 of 21")).toBeInTheDocument(); expect(screen.getByText("exact 20")).toBeInTheDocument(); expect(screen.getByRole("button", {name: "Next source records"})).toBeDisabled();
  unmount(); mount({...evidence, claims: []}); records(); expect(screen.getByText("Records 0–0 of 0")).toBeInTheDocument();
});

it("emphasizes source support while retaining observation counts and precision, including repeated claims", () => {
  const value = structuredClone(evidence); value.candidates[0].distinct_source_support_count = 1; value.candidates[0].observation_support_count = 3;
  mount(value); const candidate = screen.getByRole("region", {name: `Candidate ${value.candidates[0].canonical_clock}`});
  expect(candidate.textContent).toContain("Reported by 1 source"); expect(within(candidate).getByText("3 reports in total")).toBeInTheDocument();
  expect(within(candidate).queryByText(`${value.candidates[0].precision} precision`)).not.toBeInTheDocument();
  fireEvent.click(within(candidate).getByRole("button", {name: /View supporting reports/}));
  const panel = screen.getByRole("dialog");
  expect(panel.textContent).toContain("3 source observations · 1 distinct reporting sources"); expect(panel.textContent).toContain(`${value.candidates[0].precision} precision`);
  expect(panel.textContent).toContain(value.candidates[0].contradicting_observation_ids.join(" · "));
});
