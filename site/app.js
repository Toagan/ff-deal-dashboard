import { el, renderColumns, renderHorizontalBars, renderTable } from "./charts.js";
import * as fmt from "./format.js";

const DATA_URL = "data.json";
const VIEW_PARAM = "view";
const DEFAULT_VIEW = "all";
const STALE_AFTER_HOURS = 3;
const MS_PER_HOUR = 3_600_000;

const byId = (id) => document.getElementById(id);

function validatePayload(payload) {
  const isValid =
    payload &&
    Array.isArray(payload.views) &&
    payload.views.length > 0 &&
    Array.isArray(payload.owners) &&
    Array.isArray(payload.segments);
  if (!isValid) throw new Error("The data file has an unexpected shape.");
  return payload;
}

async function loadPayload() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`The data file could not be loaded (HTTP ${response.status}).`);
  return validatePayload(await response.json());
}

function renderKpis(kpis) {
  byId("kpi-open").textContent = fmt.money(kpis.open_pipeline);
  byId("kpi-open-note").textContent =
    `${fmt.plural(kpis.open_count, "open deal")} from Prospect to Contract Sent. ` +
    `${fmt.money(kpis.late_stage_amount)} of it sits in the last two stages.`;
  const tiles = [
    ["Weighted pipeline", fmt.money(kpis.weighted_pipeline), "by stage probability"],
    ["Live ARR", fmt.money(kpis.live_arr), fmt.plural(kpis.live_contracts, "contract")],
    ["Won this quarter", fmt.money(kpis.won_qtd_amount), fmt.plural(kpis.won_qtd_count, "deal")],
    ["Won this year", fmt.money(kpis.won_ytd_amount), fmt.plural(kpis.won_ytd_count, "deal")],
    ["Win rate, 12 months", fmt.percent(kpis.win_rate_12m), `${fmt.percent(kpis.win_rate_90d)} in the last 90 days`],
    ["Median sales cycle", fmt.days(kpis.median_cycle_days_12m), `average won deal ${fmt.money(kpis.avg_won_amount_12m)}`],
  ];
  const nodes = tiles.map(([label, value, detail]) => {
    const tile = el("div");
    tile.append(el("dt", "", label), el("dd", "value", value), el("dd", "detail", detail));
    return tile;
  });
  byId("kpi-strip").replaceChildren(...nodes);
}

function stageTooltip(stage) {
  return [
    stage.label,
    `${fmt.plural(stage.count, "deal")}, ${fmt.moneyFull(stage.amount)}`,
    `Weighted ${fmt.moneyFull(stage.weighted)} at ${fmt.percent(stage.probability)}`,
    `Median time in stage ${fmt.days(stage.median_days_in_stage)}`,
  ].join("\n");
}

function renderFunnel(stages) {
  const active = stages.filter((stage) => !stage.is_watchlist);
  const rows = active.map((stage) => ({
    label: `${stage.label} (${fmt.count(stage.count)})`,
    value: stage.amount,
    tooltip: stageTooltip(stage),
  }));
  renderHorizontalBars(byId("funnel"), rows, fmt.money);
  const parked = stages
    .filter((stage) => stage.is_watchlist)
    .map((stage) => `${stage.label}: ${fmt.plural(stage.count, "deal")}, ${fmt.money(stage.amount)}`);
  byId("watchlist").textContent = parked.length ? `Not counted as pipeline. ${parked.join(". ")}.` : "";
}

function renderHygiene(hygiene) {
  const items = [
    [hygiene.late_stage_without_next_step, `of ${fmt.count(hygiene.late_stage_count)} late-stage deals have no next step`],
    [hygiene.close_date_overdue, "open deals have a close date in the past"],
    [hygiene.no_activity_30_days, "open deals have no logged activity in 30 days"],
    [hygiene.without_amount, "open deals have no amount"],
    [hygiene.without_owner, "open deals have no owner"],
  ];
  const nodes = items.map(([value, text]) => {
    const item = el("li", value === 0 ? "is-clear" : "is-open");
    const body = el("p", "", text);
    body.prepend(el("span", "state", value === 0 ? "Clear" : "Needs attention"));
    item.append(el("span", "count", fmt.count(value)), body);
    return item;
  });
  byId("hygiene").replaceChildren(...nodes);
}

function renderSeries(view) {
  const forecast = view.forecast.map((row) => ({
    label: fmt.shortMonth(row.month),
    tooltip: `${fmt.longMonth(row.month)}\n${fmt.plural(row.count, "deal")} due\nFace value ${fmt.moneyFull(row.amount)}\nWeighted ${fmt.moneyFull(row.weighted)}`,
    values: [{ value: row.amount, isContext: true }, { value: row.weighted }],
  }));
  renderColumns(byId("forecast"), forecast, fmt.money);
  const won = view.monthly.map((row) => ({
    label: fmt.shortMonth(row.month),
    tooltip: `${fmt.longMonth(row.month)}\n${fmt.moneyFull(row.won_amount)} won\n${fmt.plural(row.won, "deal")} won, ${fmt.count(row.lost)} lost`,
    values: [{ value: row.won_amount }],
  }));
  renderColumns(byId("won"), won, fmt.money);
  const created = view.monthly.map((row) => ({
    label: fmt.shortMonth(row.month),
    tooltip: `${fmt.longMonth(row.month)}\n${fmt.plural(row.created, "deal")} created`,
    values: [{ value: row.created }],
  }));
  renderColumns(byId("created"), created, fmt.count);
}

function renderCustomerSuccess(stages) {
  const columns = [
    { header: "Stage", cell: (row) => row.label },
    { header: "Deals", cell: (row) => fmt.count(row.count) },
    { header: "Value", cell: (row) => fmt.money(row.amount) },
    { header: "Days in stage", cell: (row) => (row.count ? fmt.count(row.median_days_in_stage) : "") },
  ];
  renderTable(byId("cs-table"), columns, stages, "No Customer Success deals in this view.");
}

function renderBreakdown(tableId, firstHeader, rows) {
  const columns = [
    { header: firstHeader, cell: (row) => row.name },
    { header: "Open", cell: (row) => fmt.count(row.open_count) },
    { header: "Pipeline", cell: (row) => fmt.money(row.open_amount) },
    { header: "Weighted", cell: (row) => fmt.money(row.weighted) },
    { header: "Won this year", cell: (row) => `${fmt.money(row.won_ytd_amount)} (${fmt.count(row.won_ytd_count)})` },
  ];
  renderTable(byId(tableId), columns, rows, "Nothing to show.");
}

function renderView(view) {
  renderKpis(view.kpis);
  renderFunnel(view.sales_stages);
  renderHygiene(view.hygiene);
  renderSeries(view);
  renderCustomerSuccess(view.cs_stages);
}

function buildSelect(select, views) {
  const groups = new Map();
  views.forEach((view) => {
    const option = el("option", "", view.label);
    option.value = view.key;
    if (view.group === "All") {
      select.append(option);
      return;
    }
    if (!groups.has(view.group)) {
      const group = el("optgroup");
      group.label = view.group;
      groups.set(view.group, group);
      select.append(group);
    }
    groups.get(view.group).append(option);
  });
}

function readViewKey(views) {
  const requested = new URLSearchParams(window.location.search).get(VIEW_PARAM);
  return views.some((view) => view.key === requested) ? requested : DEFAULT_VIEW;
}

function writeViewKey(key) {
  const url = new URL(window.location.href);
  if (key === DEFAULT_VIEW) url.searchParams.delete(VIEW_PARAM);
  else url.searchParams.set(VIEW_PARAM, key);
  window.history.replaceState(null, "", url);
}

function syncedText(generatedAt) {
  const ageHours = (Date.now() - new Date(generatedAt).getTime()) / MS_PER_HOUR;
  const warning = ageHours > STALE_AFTER_HOURS ? ". The hourly sync looks stuck." : "";
  return `${fmt.synced(generatedAt)}${warning}`;
}

function start(payload) {
  const select = byId("view-select");
  const findView = (key) => payload.views.find((view) => view.key === key) ?? payload.views[0];
  buildSelect(select, payload.views);
  select.value = readViewKey(payload.views);
  select.addEventListener("change", () => {
    writeViewKey(select.value);
    renderView(findView(select.value).data);
  });
  byId("synced").textContent = syncedText(payload.generated_at);
  renderBreakdown("owner-table", "Owner", payload.owners);
  renderBreakdown("segment-table", "Segment", payload.segments);
  renderView(findView(select.value).data);
  byId("dashboard").hidden = false;
}

loadPayload()
  .then(start)
  .catch((error) => {
    byId("synced").textContent = "Not loaded";
    const message = byId("error");
    message.textContent = `The dashboard could not load. ${error.message}`;
    message.hidden = false;
  });
