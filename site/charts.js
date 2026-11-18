// Small DOM chart builders. All text goes through textContent, never innerHTML.

const GRIDLINE_COUNT = 2;
const TOOLTIP_OFFSET_PX = 14;

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const tooltip = () => document.getElementById("tooltip");

function showTooltip(text, x, y) {
  const tip = tooltip();
  tip.textContent = text;
  tip.hidden = false;
  const { width, height } = tip.getBoundingClientRect();
  const left = Math.min(x + TOOLTIP_OFFSET_PX, window.innerWidth - width - TOOLTIP_OFFSET_PX);
  const top = Math.max(TOOLTIP_OFFSET_PX, y - height - TOOLTIP_OFFSET_PX);
  tip.style.transform = `translate(${Math.max(0, left)}px, ${top}px)`;
}

function attachTooltip(node, text) {
  node.tabIndex = 0;
  node.setAttribute("aria-label", text.replaceAll("\n", ", "));
  node.addEventListener("pointermove", (event) => showTooltip(text, event.clientX, event.clientY));
  node.addEventListener("pointerleave", () => { tooltip().hidden = true; });
  node.addEventListener("focus", () => {
    const box = node.getBoundingClientRect();
    showTooltip(text, box.left + box.width / 2, box.top);
  });
  node.addEventListener("blur", () => { tooltip().hidden = true; });
}

// Round a maximum up to a tidy axis ceiling (1, 2 or 5 times a power of ten).
export function niceCeiling(value) {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 5, 10].find((multiple) => multiple * magnitude >= value);
  return step * magnitude;
}

export function renderHorizontalBars(container, rows, formatValue) {
  const max = Math.max(...rows.map((row) => row.value), 0);
  const nodes = rows.map((row) => {
    const line = el("div", "hbar-row");
    const track = el("div", "track");
    const bar = el("span", "bar");
    bar.style.width = max > 0 ? `${(row.value / max) * 100}%` : "0";
    attachTooltip(bar, row.tooltip);
    track.append(bar);
    line.append(el("span", "name", row.label), track, el("span", "value", formatValue(row.value)));
    return line;
  });
  container.replaceChildren(...nodes);
}

// rows: [{ label, tooltip, values: [{ value, isContext }] }]
export function renderColumns(container, rows, formatValue) {
  const ceiling = niceCeiling(Math.max(...rows.flatMap((row) => row.values.map((v) => v.value)), 0));
  const plot = el("div", "plot");
  for (let step = 1; step <= GRIDLINE_COUNT; step += 1) {
    const line = el("span", "gridline", formatValue((ceiling * step) / GRIDLINE_COUNT));
    line.style.bottom = `${(step / GRIDLINE_COUNT) * 100}%`;
    line.style.transform = "translateY(100%)";
    plot.append(line);
  }
  const axis = el("div", rows.length <= 6 ? "axis is-short" : "axis");
  rows.forEach((row) => {
    const column = el("div", "column");
    row.values.forEach(({ value, isContext }) => {
      const mark = el("i", isContext ? "context" : "");
      mark.style.height = `${(value / ceiling) * 100}%`;
      column.append(mark);
    });
    attachTooltip(column, row.tooltip);
    plot.append(column);
    axis.append(el("span", "", row.label));
  });
  container.replaceChildren(plot, axis);
}

// columns: [{ header, cell: (row) => string }]
export function renderTable(table, columns, rows, emptyText) {
  const head = el("thead");
  const headRow = el("tr");
  columns.forEach((column) => {
    const th = el("th", "", column.header);
    th.scope = "col";
    headRow.append(th);
  });
  head.append(headRow);
  const body = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((column) => tr.append(el("td", "", column.cell(row))));
    body.append(tr);
  });
  if (rows.length === 0) {
    const cell = el("td", "", emptyText);
    cell.colSpan = columns.length;
    const tr = el("tr");
    tr.append(cell);
    body.append(tr);
  }
  table.replaceChildren(head, body);
}
