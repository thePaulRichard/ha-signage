// Signage page: screens, playlists and media of the Signage integration.
// A plain web component (no build step) that uses Home Assistant's own elements
// and theme variables, so it looks like the rest of Home Assistant.

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmtTime = (s) => {
  if (!s && s !== 0) return "";
  s = Math.round(s);
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `${s} s`;
};
const has = (tag) => !!customElements.get(tag);

const STYLE = `
:host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif)); }
.header { position:sticky; top:0; z-index:3; background:var(--app-header-background-color); color:var(--app-header-text-color, #fff);
  border-bottom:var(--app-header-border-bottom, none); }
.toolbar { height:var(--header-height, 56px); display:flex; align-items:center; gap:4px; padding:0 12px; box-sizing:border-box; }
.toolbar .title { font-size:20px; font-weight:400; margin-left:8px; flex:1; }
.tabs { display:flex; padding:0 8px; }
.tab { background:none; border:none; color:inherit; opacity:.75; font:inherit; font-size:14px; font-weight:500; letter-spacing:.03em;
  text-transform:uppercase; padding:12px 16px; cursor:pointer; border-bottom:2px solid transparent; }
.tab.active { opacity:1; border-bottom-color:var(--app-header-text-color, #fff); }
.content { max-width:1280px; margin:0 auto; padding:16px; box-sizing:border-box; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); gap:16px; }
.card { background:var(--ha-card-background, var(--card-background-color, #fff)); border-radius:var(--ha-card-border-radius, 12px);
  border:var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
  box-shadow:var(--ha-card-box-shadow, none); overflow:hidden; }
.thumb { aspect-ratio:16/9; background:#000; display:flex; align-items:center; justify-content:center; color:#888; position:relative; }
.thumb img { width:100%; height:100%; object-fit:contain; }
.body { padding:12px 16px 16px; display:flex; flex-direction:column; gap:10px; }
.row { display:flex; align-items:center; gap:12px; justify-content:space-between; }
.name { font-size:18px; font-weight:500; }
.secondary { color:var(--secondary-text-color); font-size:14px; }
.chip { font-size:12px; font-weight:500; padding:2px 10px; border-radius:12px; white-space:nowrap; }
.chip.playing { background:rgba(var(--rgb-success-color, 67,160,71), .15); color:var(--success-color, #43a047); }
.chip.paused, .chip.stopped, .chip.off { background:rgba(var(--rgb-secondary-text-color, 114,114,114), .15); color:var(--secondary-text-color); }
.chip.offline { background:rgba(var(--rgb-error-color, 219,68,55), .15); color:var(--error-color, #db4437); }
label.field { display:flex; flex-direction:column; gap:4px; font-size:12px; color:var(--secondary-text-color); flex:1; }
select, input[type=number], input[type=text] { font:inherit; font-size:15px; color:var(--primary-text-color);
  background:var(--input-fill-color, var(--secondary-background-color)); border:none; border-bottom:1px solid var(--input-idle-line-color, var(--divider-color));
  border-radius:4px 4px 0 0; padding:10px 12px; min-width:0; width:100%; box-sizing:border-box; }
select:focus, input:focus { outline:none; border-bottom:2px solid var(--primary-color); }
.btn { font:inherit; font-size:14px; font-weight:500; border:none; border-radius:20px; padding:9px 20px; cursor:pointer;
  background:var(--primary-color); color:var(--text-primary-color, #fff); display:inline-flex; align-items:center; gap:6px; }
.btn.text { background:none; color:var(--primary-color); padding:9px 12px; }
.btn.danger { background:none; color:var(--error-color, #db4437); }
.btn:disabled { opacity:.5; cursor:default; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
.pchip { font:inherit; font-size:14px; border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color);
  border-radius:18px; padding:7px 16px; cursor:pointer; }
.pchip.active { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
.editor .fields { display:flex; flex-wrap:wrap; gap:16px; align-items:flex-end; padding:16px; border-bottom:1px solid var(--divider-color); }
.editor .fields .field.name { flex:2; min-width:200px; }
.editor .fields .field.secs { flex:0 0 150px; }
.editor .fields .hint { flex-basis:100%; font-size:12px; margin-top:-8px; }
.toggle { display:flex; align-items:center; gap:8px; font-size:14px; padding-bottom:8px; }
.files { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:12px; padding:16px; }
.tile { border-radius:8px; overflow:hidden; cursor:pointer; border:2px solid transparent; background:var(--secondary-background-color); position:relative; }
.tile.selected { border-color:var(--primary-color); }
.tile.off .thumb img { opacity:.45; }
.tile .label { font-size:13px; padding:6px 8px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tile .check { position:absolute; top:6px; right:6px; color:var(--primary-color); background:var(--card-background-color); border-radius:50%; line-height:0; }
.tile .badge, .thumb .badge { position:absolute; left:6px; bottom:6px; background:rgba(0,0,0,.65); color:#fff; font-size:11px; padding:2px 6px; border-radius:4px; }
.card.editor { overflow:visible; }
.editbar { position:sticky; top:var(--sticky-top, 0px); z-index:2; display:flex; gap:8px; align-items:center; flex-wrap:wrap;
  padding:10px 16px; border-bottom:1px solid var(--divider-color); background:var(--ha-card-background, var(--card-background-color, #fff));
  border-radius:var(--ha-card-border-radius, 12px) var(--ha-card-border-radius, 12px) 0 0; }
.editbar.stuck { border-radius:0; box-shadow:0 2px 4px rgba(0,0,0,.12); }
.editbar .spacer { flex:1; }
.chip.dirty { background:rgba(var(--rgb-warning-color, 255,166,0), .18); color:var(--warning-color, #ffa600); }
.pick { display:flex; gap:4px; align-items:center; padding:12px 16px 0; }
.pick .secondary { flex:1; font-size:13px; }
.section-title { font-size:14px; color:var(--secondary-text-color); margin:4px 0 12px; }
.empty { padding:32px; text-align:center; color:var(--secondary-text-color); }
.uploadbar { display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap:wrap; }
.progress { flex-basis:100%; height:6px; border-radius:3px; background:var(--divider-color); overflow:hidden; }
.progress > div { height:100%; background:var(--primary-color); transition:width .2s; }
.media .tile { cursor:default; }
.content.dropping { outline:2px dashed var(--primary-color); outline-offset:-8px; border-radius:12px; }
.sched { border-top:1px solid var(--divider-color); margin:4px -16px -16px; padding:10px 16px 14px; display:flex; flex-direction:column; gap:10px; }
.sched .row .secondary { flex:1; }
.days { display:flex; gap:6px; flex-wrap:wrap; }
.day { font:inherit; font-size:13px; width:38px; height:32px; border-radius:16px; border:1px solid var(--divider-color);
  background:none; color:var(--primary-text-color); cursor:pointer; padding:0; }
.modes { display:flex; border:1px solid var(--divider-color); border-radius:18px; overflow:hidden; align-self:flex-start; }
.mode { font:inherit; font-size:13px; padding:6px 16px; background:none; border:none; color:var(--primary-text-color); cursor:pointer; }
.mode + .mode { border-left:1px solid var(--divider-color); }
.mode:disabled { opacity:.45; cursor:default; }
.daysrc { justify-content:flex-start; }
.mode.on { background:var(--primary-color); color:var(--text-primary-color, #fff); }
.card.disabled .thumb, .card.disabled .body > :not(:first-child) { opacity:.5; }
.day.on { background:var(--primary-color); border-color:var(--primary-color); color:var(--text-primary-color, #fff); }
input[type=time] { font:inherit; font-size:15px; color:var(--primary-text-color); background:var(--input-fill-color, var(--secondary-background-color));
  border:none; border-bottom:1px solid var(--divider-color); border-radius:4px 4px 0 0; padding:8px 10px; color-scheme:light dark; }
.media .tile .meta { font-size:12px; color:var(--secondary-text-color); padding:0 8px 8px; display:flex; justify-content:space-between; align-items:center; gap:4px; }
.media .tile .meta button { background:none; border:none; color:var(--error-color, #db4437); cursor:pointer; padding:2px; line-height:0; }
`;

class SignagePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "screens";
    this._data = null;
    this._selected = null; // playlist being edited (name, or "" for a new one)
    this._draft = null;
    this._busy = false;
    this._beforeUnload = (e) => { if (this._dirty()) { e.preventDefault(); e.returnValue = ""; } };
    this._keydown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s" && this._tab === "playlists" && this._draft) {
        e.preventDefault();
        this._savePlaylist();
      }
    };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._renderShell();
      this._refresh();
    }
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
  }

  set panel(_p) {}

  connectedCallback() {
    this._timer = setInterval(() => this._refresh(true), 10000);
    window.addEventListener("beforeunload", this._beforeUnload);
    window.addEventListener("keydown", this._keydown);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    window.removeEventListener("beforeunload", this._beforeUnload);
    window.removeEventListener("keydown", this._keydown);
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }

  async _call(msg, okMessage) {
    try {
      const result = await this._hass.callWS(msg);
      if (okMessage) this._toast(okMessage);
      setTimeout(() => this._refresh(), 1500); // saving reloads the integration
      return result ?? true;
    } catch (err) {
      this._toast(err.message || String(err));
      return null;
    }
  }

  async _refresh(background = false) {
    if (!this._hass || (background && document.hidden)) return;
    try {
      this._data = await this._hass.callWS({ type: "ha_signage/state" });
    } catch (err) {
      if (!background) this._content.innerHTML = `<div class="empty">${esc(err.message || err)}</div>`;
      return;
    }
    // keep a playlist being edited; otherwise show the first one
    if (this._selected === null && this._data.playlists.length) this._selectPlaylist(this._data.playlists[0].name);
    // don't redraw under the user's edits
    if (background && (this._tab === "playlists" || (this._tab === "screens" && this._editing))) return;
    this._render();
  }

  _renderShell() {
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="header">
        <div class="toolbar">
          ${has("ha-menu-button") ? "<ha-menu-button></ha-menu-button>" : ""}
          <div class="title">Signage</div>
        </div>
        <div class="tabs">
          <button class="tab" data-tab="screens">Screens</button>
          <button class="tab" data-tab="playlists">Playlists</button>
          <button class="tab" data-tab="media">Media</button>
        </div>
      </div>
      <div class="content"><div class="empty">Loading…</div></div>`;
    this._content = this.shadowRoot.querySelector(".content");
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) { menu.hass = this._hass; menu.narrow = this._narrow; }
    this.shadowRoot.querySelectorAll(".tab").forEach((tab) =>
      tab.addEventListener("click", () => { this._tab = tab.dataset.tab; this._render(); }));
    // drop pictures or videos anywhere on the Media tab to upload them
    const dropping = (e) => this._tab === "media" && !this._busy && [...(e.dataTransfer?.types || [])].includes("Files");
    this._content.addEventListener("dragover", (e) => {
      if (!dropping(e)) return;
      e.preventDefault();
      this._content.classList.add("dropping");
    });
    this._content.addEventListener("dragleave", (e) => {
      if (!this._content.contains(e.relatedTarget)) this._content.classList.remove("dropping");
    });
    this._content.addEventListener("drop", (e) => {
      this._content.classList.remove("dropping");
      if (!dropping(e)) return;
      e.preventDefault();
      const list = [...e.dataTransfer.files].filter((f) => /^(image|video)\//.test(f.type));
      if (list.length) this._upload(list);
      else this._toast("Only pictures and videos can be uploaded");
    });
  }

  _render() {
    this.shadowRoot.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === this._tab));
    if (!this._data) return;
    if (this._tab === "screens") this._renderScreens();
    else if (this._tab === "playlists") this._renderPlaylists();
    else this._renderMedia();
  }

  _switch(checked, onChange) {
    if (has("ha-switch")) {
      const sw = document.createElement("ha-switch");
      sw.checked = checked;
      sw.addEventListener("change", () => onChange(sw.checked));
      return sw;
    }
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = checked;
    box.addEventListener("change", () => onChange(box.checked));
    return box;
  }

  // ------------------------------------------------------------ screens

  _renderScreens() {
    const { screens, playlists, default_schedule: def } = this._data;
    const stateText = { playing: "Playing", paused: "Paused", stopped: "Stopped", off: "Off", offline: "Offline" };
    const modeText = { default: "Default schedule", own: "Own schedule", none: "No schedule" };
    const defaultCard = `
      <div class="card default-card" style="margin-bottom:16px">
        <div class="body">
          <div class="row"><ha-icon icon="mdi:calendar-clock" style="color:var(--secondary-text-color)"></ha-icon>
            <div style="flex:1"><div class="name" style="font-size:16px">Default schedule</div>
              <div class="secondary">${esc(def.text)} · ${((n) => `${n} screen${n === 1 ? "" : "s"}`)(screens.filter((s) => s.mode === "default").length)}</div></div>
            <button class="btn text edit-default">${this._editing === "__default" ? "Close" : "Change"}</button></div>
          ${this._editing === "__default" ? this._timesEditor(this._sched, "Keep screens on during these hours") +
            `<div class="row" style="justify-content:flex-end"><button class="btn save-default">Save</button></div>` : ""}
        </div>
      </div>`;
    if (!screens.length) {
      this._content.innerHTML = defaultCard + `<div class="empty">No screens yet. An admin adds them in Settings › Devices & services › Signage › Configure.</div>`;
      this._bindDefault(def);
      return;
    }
    const listSecs = (s) => (playlists.find((p) => p.name === s.playlist) || {}).picture_seconds;
    this._content.innerHTML = defaultCard + `<div class="grid">${screens.map((s) => `
      <div class="card ${s.enabled ? "" : "disabled"}" data-id="${esc(s.id)}">
        <div class="thumb">${s.now_thumb && s.enabled ? `<img src="${esc(s.now_thumb)}" alt="">` : `<ha-icon icon="${s.enabled ? "mdi:television" : "mdi:television-off"}"></ha-icon>`}</div>
        <div class="body">
          <div class="row"><div class="name">${esc(s.name)}</div><span class="enable-slot"></span></div>
          <div class="row"><div class="secondary">${!s.enabled ? "Disabled" : s.now_title ? `Showing ${esc(s.now_title)}` : s.kind === "pc" ? "Wall PC" : "Cast TV"}</div>
            ${s.enabled ? `<span class="chip ${esc(s.state)}">${stateText[s.state] || esc(s.state)}</span>` : ""}</div>
          <div class="row">
            <label class="field">Playlist
              <select class="playlist">${playlists.map((p) => `<option ${p.name === s.playlist ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
            </label>
            <label class="field" style="flex:0 0 130px">Display time (s)
              <input class="secs" type="number" min="0" value="${s.picture_seconds || ""}"
                placeholder="${listSecs(s) ? `Default: ${listSecs(s)}` : "Default"}"
                title="How long each picture stays up; videos always play to the end. Leave empty to use the ${esc(s.playlist || "")} playlist's ${listSecs(s) || ""} s; a number here overrides it for this screen only.">
            </label>
          </div>
          <div class="sched">
            <div class="row"><ha-icon icon="mdi:calendar-clock" style="color:var(--secondary-text-color)"></ha-icon>
              <span class="secondary">${modeText[s.mode]}${s.mode === "own" ? ` · ${esc(s.schedule_text)}` : ""}</span>
              <button class="btn text edit-sched">${this._editing === s.id ? "Close" : "Change"}</button></div>
            ${s.enabled && s.mode === "none" && s.kind !== "pc" ? `<div class="row" style="justify-content:flex-end">
              <button class="btn text startstop">${s.state === "playing" ? "Stop" : "Start"}</button></div>` : ""}
            ${this._editing === s.id ? this._scheduleEditor(s) : ""}
          </div>
        </div>
      </div>`).join("")}</div>`;
    this._bindDefault(def);
    this._content.querySelectorAll(".card[data-id]").forEach((card) => {
      const s = screens.find((x) => x.id === card.dataset.id);
      card.querySelector(".enable-slot").replaceWith(this._switch(s.enabled, (on) =>
        this._call({ type: "ha_signage/set_enabled", screen_id: s.id, enabled: on }, `${s.name} ${on ? "enabled" : "disabled"}`)));
      card.querySelector(".playlist").addEventListener("change", (e) =>
        this._call({ type: "ha_signage/set_screen", screen_id: s.id, playlist: e.target.value }, `${s.name}: playlist ${e.target.value}`));
      card.querySelector(".secs").addEventListener("change", (e) =>
        this._call({ type: "ha_signage/set_screen", screen_id: s.id, picture_seconds: Number(e.target.value) || 0 },
          Number(e.target.value) ? `${s.name}: display time ${e.target.value} s` : `${s.name}: playlist's display time`));
      card.querySelector(".edit-sched").addEventListener("click", () => {
        this._editing = this._editing === s.id ? null : s.id;
        this._sched = { mode: s.mode, ...s.schedule, days: [...s.schedule.days], workday_entity: s.workday_entity || null };
        this._renderScreens();
      });
      card.querySelector(".startstop")?.addEventListener("click", () =>
        this._call({ type: "ha_signage/screen_power", screen_id: s.id, on: s.state !== "playing" }, `${s.name} ${s.state === "playing" ? "stopped" : "started"}`));
      if (this._editing === s.id) this._bindScheduleEditor(card, s);
    });
  }

  _bindDefault(def) {
    const card = this._content.querySelector(".default-card");
    card.querySelector(".edit-default").addEventListener("click", () => {
      this._editing = this._editing === "__default" ? null : "__default";
      this._sched = { ...def, days: [...def.days] };
      this._renderScreens();
    });
    if (this._editing !== "__default") return;
    const d = this._sched;
    this._bindTimes(card, d);
    card.querySelector(".save-default").addEventListener("click", async () => {
      if (!d.workday_entity && !d.days.length) return this._toast("Pick at least one day");
      if (await this._call({ type: "ha_signage/set_default_schedule", days: d.days, start: d.start.slice(0, 5),
        end: d.end.slice(0, 5), keep_on: !!d.keep_on, workday_entity: d.workday_entity || null }, "Default schedule saved")) this._editing = null;
    });
  }

  // Workday sensors to offer, plus the one in use if it's some other on/off entity
  _workdays(d) {
    const list = [...(this._data.workday_sensors || [])];
    if (d.workday_entity && !list.some((w) => w.entity_id === d.workday_entity)) {
      const st = this._hass.states[d.workday_entity];
      list.push({ entity_id: d.workday_entity, name: st?.attributes.friendly_name || d.workday_entity });
    }
    return list;
  }

  _timesEditor(d, keepLabel) {
    const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const sensors = this._workdays(d);
    const current = sensors.find((w) => w.entity_id === d.workday_entity);
    return `
      <div class="row daysrc"><span class="secondary">Days</span>
        <div class="modes">
          <button class="mode src ${d.workday_entity ? "on" : ""}" data-src="workday" ${sensors.length ? ""
            : `disabled title="Add the Workday integration in Settings › Devices & services first"`}>Workdays</button>
          <button class="mode src ${d.workday_entity ? "" : "on"}" data-src="days">Pick days</button>
        </div></div>
      ${d.workday_entity ? (sensors.length > 1
        ? `<label class="field">Workday sensor<select class="workday">${sensors.map((w) =>
            `<option value="${esc(w.entity_id)}" ${w.entity_id === d.workday_entity ? "selected" : ""}>${esc(w.name)}</option>`).join("")}</select></label>`
        : `<div class="secondary" style="font-size:12px">Runs on the days ${esc(current?.name || d.workday_entity)} counts as workdays, so public holidays are skipped too.</div>`)
      : `<div class="days">${names.map((n, i) => `<button class="day ${d.days.includes(i) ? "on" : ""}" data-day="${i}">${n}</button>`).join("")}</div>`}
      <div class="row">
        <label class="field">Start<input type="time" class="start" value="${esc(d.start)}"></label>
        <label class="field">End<input type="time" class="end" value="${esc(d.end)}"></label>
      </div>
      <div class="secondary midnight" style="font-size:12px" ${this._overnight(d) ? "" : "hidden"}>Ends the next day: the end is before the start.</div>
      <div class="row"><span class="secondary">${keepLabel}<br><span style="font-size:12px">Starts it again if someone stops it or the TV drops out</span></span><span class="keep-switch"></span></div>`;
  }

  _overnight(d) {
    return !!(d.start && d.end && d.end.slice(0, 5) < d.start.slice(0, 5));
  }

  _bindTimes(root, d) {
    root.querySelectorAll(".src").forEach((b) => b.addEventListener("click", () => {
      const sensors = this._workdays(d);
      if (b.dataset.src === "workday") d.workday_entity = d.workday_entity || this._lastWorkday || sensors[0]?.entity_id || null;
      else { if (d.workday_entity) this._lastWorkday = d.workday_entity; d.workday_entity = null; }
      this._renderScreens();
    }));
    root.querySelector(".workday")?.addEventListener("change", (e) => (d.workday_entity = e.target.value));
    root.querySelectorAll(".day").forEach((b) => b.addEventListener("click", () => {
      const day = Number(b.dataset.day);
      d.days = d.days.includes(day) ? d.days.filter((x) => x !== day) : [...d.days, day];
      b.classList.toggle("on");
    }));
    const midnight = () => (root.querySelector(".midnight").hidden = !this._overnight(d));
    root.querySelector(".start").addEventListener("input", (e) => { d.start = e.target.value; midnight(); });
    root.querySelector(".end").addEventListener("input", (e) => { d.end = e.target.value; midnight(); });
    root.querySelector(".keep-switch").replaceWith(this._switch(!!d.keep_on, (on) => (d.keep_on = on)));
  }

  _scheduleEditor(s) {
    const d = this._sched;
    const modes = [["default", "Default"], ["own", "Own"], ["none", "None"]];
    return `
      <div class="modes">${modes.map(([m, label]) => `<button class="mode ${d.mode === m ? "on" : ""}" data-mode="${m}">${label}</button>`).join("")}</div>
      ${d.mode === "own" ? this._timesEditor(d, "Keep it on during these hours") : `<div class="secondary" style="font-size:12px">${d.mode === "default"
        ? "Follows the default schedule at the top of this page." : "Started and stopped by hand, here or with its switch."}</div>`}
      ${s.power_name ? `<div class="secondary" style="font-size:12px">Turns ${esc(s.power_name)} on at the start and off at the end.</div>` : ""}
      <div class="row" style="justify-content:flex-end"><button class="btn save-sched">Save</button></div>`;
  }

  _bindScheduleEditor(card, s) {
    const d = this._sched;
    card.querySelectorAll(".mode").forEach((b) => b.addEventListener("click", () => { d.mode = b.dataset.mode; this._renderScreens(); }));
    if (d.mode === "own") this._bindTimes(card.querySelector(".sched"), d);
    card.querySelector(".save-sched").addEventListener("click", async () => {
      if (d.mode === "own" && !d.workday_entity && !d.days.length) return this._toast("Pick at least one day");
      const ok = await this._call({ type: "ha_signage/set_schedule", screen_id: s.id, mode: d.mode,
        days: d.days, start: d.start.slice(0, 5), end: d.end.slice(0, 5), keep_on: !!d.keep_on,
        ...(d.mode === "own" ? { workday_entity: d.workday_entity || null } : {}) }, `${s.name}: schedule saved`);
      if (ok) this._editing = null;
    });
  }

  // ------------------------------------------------------------ playlists

  _selectPlaylist(name) {
    this._selected = name;
    const pl = this._data.playlists.find((p) => p.name === name);
    this._draft = pl
      ? { old_name: pl.name, name: pl.name, files: new Set(pl.files), picture_seconds: pl.picture_seconds, shuffle: pl.shuffle }
      : { old_name: null, name: "", files: new Set(), picture_seconds: 150, shuffle: true };
    this._draft.base = this._draftKey(this._draft);
  }

  _draftKey(d) {
    return JSON.stringify([d.name.trim(), [...d.files].sort(), Number(d.picture_seconds), !!d.shuffle]);
  }

  // true when the playlist editor has changes that aren't saved yet
  _dirty() {
    return !!this._draft && this._draftKey(this._draft) !== this._draft.base;
  }

  // "12 files · about 34 min a loop · on ONE TV, TWO TV"
  _playlistSummary(d) {
    const { files, screens } = this._data;
    const users = d.old_name ? screens.filter((s) => s.playlist === d.old_name).map((s) => s.name) : [];
    let secs = 0;
    for (const f of files) {
      if (!d.files.has(f.name)) continue;
      secs += f.kind === "video" ? f.duration || 0 : Number(d.picture_seconds) || 0;
    }
    const loop = secs >= 60 ? ` · about ${Math.round(secs / 60)} min a loop` : secs ? ` · ${Math.round(secs)} s a loop` : "";
    return `${d.files.size} file${d.files.size === 1 ? "" : "s"}${loop}${users.length ? ` · on ${users.map(esc).join(", ")}` : ""}`;
  }

  // refresh the bar at the top of the editor without redrawing the thumbnails
  _updateEditbar() {
    const d = this._draft;
    const bar = this._content.querySelector(".editbar");
    if (!bar || !d) return;
    const dirty = this._dirty();
    bar.querySelector(".summary").innerHTML = this._playlistSummary(d);
    bar.querySelector(".chip.dirty").hidden = !dirty || !d.old_name;
    bar.querySelector(".save").disabled = !!d.old_name && !dirty;
  }

  _renderPlaylists() {
    const { playlists, files } = this._data;
    const d = this._draft || (this._selectPlaylist(""), this._draft);
    const known = new Set(files.map((f) => f.name));
    const missing = [...d.files].filter((f) => !known.has(f));
    this._content.innerHTML = `
      <div class="chips">
        ${playlists.map((p) => `<button class="pchip ${p.name === d.old_name ? "active" : ""}" data-name="${esc(p.name)}">${esc(p.name)}</button>`).join("")}
        <button class="pchip ${d.old_name === null ? "active" : ""}" data-name=""><ha-icon icon="mdi:plus" style="--mdc-icon-size:18px;vertical-align:-3px"></ha-icon> New playlist</button>
      </div>
      <div class="card editor">
        <div class="editbar">
          <span class="secondary summary"></span>
          <span class="chip dirty" hidden>Unsaved changes</span>
          <span class="spacer"></span>
          ${d.old_name ? `<button class="btn danger delete">Delete</button>` : ""}
          <button class="btn save" title="Ctrl+S"><ha-icon icon="mdi:content-save" style="--mdc-icon-size:18px"></ha-icon> ${d.old_name ? "Save" : "Create"}</button>
        </div>
        <div class="fields">
          <label class="field name">Name<input type="text" class="pname" value="${esc(d.name)}" placeholder="For example Kitchen"></label>
          <label class="field secs" title="How long each picture stays up">Display time (s)<input type="number" class="psecs" min="1" value="${d.picture_seconds}"></label>
          <div class="toggle"><span class="shuffle-slot"></span>Random order</div>
          <div class="secondary hint">Display time is for pictures: videos always play to the end.</div>
        </div>
        ${files.length ? `<div class="pick"><span class="secondary">Tap a picture or video to add it or take it out.</span>
          <button class="btn text all">Select all</button><button class="btn text none">Clear</button></div>` : ""}
        <div class="files">${files.length ? files.map((f) => `
          <div class="tile ${d.files.has(f.name) ? "selected" : "off"}" data-name="${esc(f.name)}" title="${esc(f.name)}">
            <div class="thumb">${f.thumb ? `<img src="${esc(f.thumb)}" loading="lazy" alt="">` : `<ha-icon icon="mdi:file-image"></ha-icon>`}
              ${f.kind === "video" ? `<span class="badge">▶ ${fmtTime(f.duration)}</span>` : ""}</div>
            <span class="check"><ha-icon icon="mdi:check-circle"></ha-icon></span>
            <div class="label">${esc(f.title)}</div>
          </div>`).join("") : `<div class="empty">No pictures or videos yet: add some in the Media tab.</div>`}
        </div>
        ${missing.length ? `<div class="secondary" style="padding:0 16px 12px">Missing from the media folder (skipped): ${missing.map(esc).join(", ")}</div>` : ""}
      </div>`;
    const c = this._content;
    // the bar sticks under the page header, which is taller when the tabs wrap
    const header = this.shadowRoot.querySelector(".header");
    this.style.setProperty("--sticky-top", `${header ? header.offsetHeight : 0}px`);
    const bar = c.querySelector(".editbar");
    const tiles = c.querySelectorAll(".tile");
    const paint = (t) => {
      const on = d.files.has(t.dataset.name);
      t.classList.toggle("selected", on);
      t.classList.toggle("off", !on);
      t.querySelector(".check").hidden = !on;
    };
    tiles.forEach(paint);
    this._updateEditbar();
    if (this._stuck) this._stuck.disconnect();
    this._stuck = new IntersectionObserver(([e]) => bar.classList.toggle("stuck", e.intersectionRatio < 1),
      { rootMargin: `-${header ? header.offsetHeight + 1 : 1}px 0px 0px 0px`, threshold: [1] });
    this._stuck.observe(bar);

    c.querySelectorAll(".pchip").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.name === (d.old_name ?? "")) return;
      if (this._dirty() && !confirm(`Discard the changes to ${d.old_name || "the new playlist"}?`)) return;
      this._selectPlaylist(b.dataset.name);
      this._renderPlaylists();
    }));
    c.querySelector(".pname").addEventListener("input", (e) => { d.name = e.target.value; this._updateEditbar(); });
    c.querySelector(".psecs").addEventListener("input", (e) => { d.picture_seconds = Number(e.target.value); this._updateEditbar(); });
    c.querySelector(".shuffle-slot").replaceWith(this._switch(d.shuffle, (on) => { d.shuffle = on; this._updateEditbar(); }));
    tiles.forEach((t) => t.addEventListener("click", () => {
      d.files.has(t.dataset.name) ? d.files.delete(t.dataset.name) : d.files.add(t.dataset.name);
      paint(t);
      this._updateEditbar();
    }));
    c.querySelector(".all")?.addEventListener("click", () => { files.forEach((f) => d.files.add(f.name)); tiles.forEach(paint); this._updateEditbar(); });
    c.querySelector(".none")?.addEventListener("click", () => { d.files.clear(); tiles.forEach(paint); this._updateEditbar(); });
    c.querySelector(".save").addEventListener("click", () => this._savePlaylist());
    c.querySelector(".delete")?.addEventListener("click", async () => {
      if (!confirm(`Delete the playlist ${d.old_name}?`)) return;
      if (await this._call({ type: "ha_signage/delete_playlist", name: d.old_name }, `Playlist ${d.old_name} deleted`)) {
        this._selected = null; this._draft = null;
      }
    });
  }

  async _savePlaylist() {
    const d = this._draft;
    if (this._saving || (d.old_name && !this._dirty())) return;
    if (!d.name.trim()) return this._toast("Give the playlist a name");
    if (!(d.picture_seconds >= 1)) return this._toast("Display time needs at least 1 second");
    const { files } = this._data;
    const known = new Set(files.map((f) => f.name));
    this._saving = true;
    const ok = await this._call({
      type: "ha_signage/save_playlist", ...(d.old_name ? { old_name: d.old_name } : {}),
      name: d.name.trim(), files: files.map((f) => f.name).filter((n) => d.files.has(n)).concat([...d.files].filter((n) => !known.has(n))),
      picture_seconds: Math.round(d.picture_seconds), shuffle: d.shuffle,
    }, `Playlist ${d.name.trim()} saved`);
    this._saving = false;
    if (ok) {
      this._selected = d.name.trim();
      d.name = d.name.trim();
      d.old_name = d.name;
      d.base = this._draftKey(d);
      if (this._tab === "playlists") this._renderPlaylists();
    }
  }

  // ------------------------------------------------------------ media

  _renderMedia() {
    const { files, playlists } = this._data;
    const usedBy = (name) => playlists.filter((p) => p.files.includes(name)).map((p) => p.name);
    this._content.innerHTML = `
      <div class="uploadbar">
        <button class="btn upload" ${this._busy ? "disabled" : ""}><ha-icon icon="mdi:upload" style="--mdc-icon-size:18px"></ha-icon> Upload pictures or videos</button>
        <span class="secondary status">${this._busy ? esc(this._busy) : `${files.length} files · or drop them here · then add them to a playlist`}</span>
        <input type="file" multiple accept="image/*,video/*" hidden>
        ${this._busy && this._progress != null ? `<div class="progress"><div style="width:${this._progress}%"></div></div>` : ""}
      </div>
      <div class="files media" style="padding:0">${files.map((f) => {
        const used = usedBy(f.name);
        return `<div class="tile" title="${esc(f.name)}">
          <div class="thumb">${f.thumb ? `<img src="${esc(f.thumb)}" loading="lazy" alt="">` : `<ha-icon icon="mdi:file-image"></ha-icon>`}
            ${f.kind === "video" ? `<span class="badge">▶ ${fmtTime(f.duration)}</span>` : ""}</div>
          <div class="label">${esc(f.title)}</div>
          <div class="meta"><span>${used.length ? esc(used.join(", ")) : "Not in a playlist"}</span>
            ${used.length ? "" : `<button class="del" data-name="${esc(f.name)}" title="Delete this file"><ha-icon icon="mdi:delete-outline" style="--mdc-icon-size:18px"></ha-icon></button>`}</div>
        </div>`; }).join("")}</div>`;
    const input = this._content.querySelector("input[type=file]");
    this._content.querySelector(".upload").addEventListener("click", () => input.click());
    input.addEventListener("change", () => this._upload([...input.files]));
    this._content.querySelectorAll(".del").forEach((b) => b.addEventListener("click", async () => {
      if (!confirm(`Delete ${b.dataset.name} from the media folder?`)) return;
      await this._call({ type: "ha_signage/delete_file", name: b.dataset.name }, `${b.dataset.name} deleted`);
    }));
  }

  async _upload(list) {
    let done = 0;
    for (const [index, file] of list.entries()) {
      const label = `Uploading ${file.name}${list.length > 1 ? ` (${index + 1} of ${list.length})` : ""}`;
      this._busy = `${label}…`;
      this._progress = 0;
      this._renderMedia();
      try {
        const { status, body } = await this._send(file, (loaded, total) => {
          this._progress = Math.round((loaded / total) * 100);
          this._busy = loaded < total
            ? `${label}: ${this._progress}% · ${fmtSize(loaded)} of ${fmtSize(total)}`
            : `${label}: processing…`;
          const bar = this._content.querySelector(".progress > div");
          const text = this._content.querySelector(".uploadbar .status");
          if (bar) bar.style.width = `${this._progress}%`;
          if (text) text.textContent = this._busy;
        });
        if (status >= 200 && status < 300) done++;
        else this._toast(body.message || `Upload failed (${status})`);
      } catch (err) {
        this._toast(`Upload failed: ${err.message || err}`);
      }
    }
    this._busy = false;
    this._progress = null;
    if (done) this._toast(`${done} file${done === 1 ? "" : "s"} uploaded`);
    await this._refresh();
  }

  // XMLHttpRequest, not fetch: fetch can't report upload progress.
  async _send(file, onProgress) {
    const auth = this._hass.auth;
    if (auth.expired) await auth.refreshAccessToken();
    const form = new FormData();
    form.append("file", file);
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/ha_signage/upload");
      xhr.setRequestHeader("Authorization", `Bearer ${auth.data.access_token}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded, e.total); };
      xhr.onload = () => {
        let body = {};
        try { body = JSON.parse(xhr.responseText); } catch (_) { /* not JSON */ }
        resolve({ status: xhr.status, body });
      };
      xhr.onerror = () => reject(new Error("network error"));
      xhr.send(form);
    });
  }
}

function fmtSize(bytes) {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  return `${Math.max(1, Math.round(bytes / 1e3))} kB`;
}

customElements.define("ha-signage-panel", SignagePanel);
