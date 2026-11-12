/*
 * Coffee Machine Card — bundled with the coffee_machine integration.
 * Loaded automatically; no need to add it as a dashboard resource.
 *
 * type: custom:coffee-machine-card
 * entity: sensor.coffee_machine_status   # required
 * name: Silvia                           # optional
 * image: /local/coffee/my-machine.png    # optional (put the file in config/www/coffee/)
 * show_power: true                       # optional, show the plug on/off button
 */

// The integration loads this file as a module with ?v=<manifest version>.
const CARD_VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";

const STATES = {
  off: { label: "Off", sub: "Smart plug is off" },
  waking: { label: "Waking up", sub: "Power-cycling the plug…" },
  heating: { label: "Heating up", sub: null },
  ready: { label: "Ready", sub: null },
  sleeping: { label: "Sleeping", sub: "Gone to standby — tap Wake to heat up" },
  unavailable: { label: "Unavailable", sub: "Check the smart plug" },
};

const FALLBACK_IMAGE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <rect x="40" y="30" width="120" height="30" rx="8" fill="#6d4c41"/>
  <rect x="50" y="60" width="100" height="90" rx="6" fill="#8d6e63"/>
  <rect x="80" y="60" width="40" height="22" rx="4" fill="#4e342e"/>
  <rect x="96" y="82" width="8" height="18" fill="#4e342e"/>
  <path d="M78 112h44v26a10 10 0 0 1-10 10H88a10 10 0 0 1-10-10z" fill="#efebe9"/>
  <path d="M122 118h8a8 8 0 0 1 0 16h-8" fill="none" stroke="#efebe9" stroke-width="5"/>
  <rect x="35" y="150" width="130" height="14" rx="6" fill="#5d4037"/>
</svg>`);

const fmt = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
};

class CoffeeMachineCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("coffee-machine-card-editor");
  }

  static getStubConfig(hass) {
    const entity =
      Object.values(hass.entities || {}).find(
        (e) => e.platform === "coffee_machine" && e.entity_id.startsWith("sensor.") &&
          hass.states[e.entity_id]?.attributes?.options?.includes("heating")
      )?.entity_id || "";
    return { entity, image: "", show_power: true };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Choose your coffee machine's Status entity");
    }
    this._config = { show_power: true, ...config };
    this._build();
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._root) this._update();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }

  connectedCallback() {
    this._timer = setInterval(() => this._updateTime(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  _build() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .hero { position: relative; display: flex; justify-content: center; align-items: center;
                padding: 20px 16px 8px; cursor: pointer; min-height: 160px; }
        .hero::before { content: ""; position: absolute; width: 70%; aspect-ratio: 1; border-radius: 50%;
                filter: blur(30px); opacity: 0; transition: opacity .6s, background .6s; }
        .hero img { position: relative; max-width: 100%; max-height: 220px; object-fit: contain;
                transition: filter .6s, opacity .6s, transform .6s; }
        .off .hero img { filter: grayscale(1); opacity: .45; }
        .sleeping .hero img { filter: grayscale(.8) brightness(.85); opacity: .7; }
        .waking .hero img { filter: grayscale(.4); opacity: .85; }
        .heating .hero::before { background: #ff7043; opacity: .35; animation: pulse 2.4s ease-in-out infinite; }
        .ready .hero::before { background: #66bb6a; opacity: .28; }
        .unavailable .hero img { filter: grayscale(1); opacity: .3; }
        @keyframes pulse { 0%,100% { opacity: .18; transform: scale(.92); } 50% { opacity: .45; transform: scale(1.04); } }

        .info { padding: 4px 16px 0; }
        .name { font-size: 1.15rem; font-weight: 500; color: var(--primary-text-color); }
        .status { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-weight: 500; }
        .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--disabled-text-color); }
        .heating .dot { background: #ff7043; animation: blink 1.2s infinite; }
        .ready .dot { background: #43a047; }
        .waking .dot { background: #ffa726; animation: blink .6s infinite; }
        .sleeping .dot { background: #7e57c2; }
        @keyframes blink { 50% { opacity: .3; } }
        .sub { color: var(--secondary-text-color); font-size: .9rem; margin-top: 2px; min-height: 1.2em; }

        .bar { height: 4px; margin: 12px 16px 0; border-radius: 2px; background: var(--divider-color); overflow: hidden; }
        .bar > div { height: 100%; width: 0; background: var(--primary-color); transition: width 1s linear; }
        .heating .bar > div { background: #ff7043; }
        .ready .bar > div { background: #43a047; }
        .bar.hidden { visibility: hidden; }

        .actions { display: flex; gap: 8px; padding: 12px 16px 16px; }
        button { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
                 border: none; border-radius: 12px; padding: 10px 12px; font: inherit; font-weight: 500;
                 cursor: pointer; background: var(--secondary-background-color); color: var(--primary-text-color); }
        button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        button[hidden] { display: none; }
        button:disabled { opacity: .5; cursor: default; }
        ha-icon { --mdc-icon-size: 20px; }
      </style>
      <ha-card>
        <div class="root">
          <div class="hero"><img alt=""></div>
          <div class="info">
            <div class="name"></div>
            <div class="status"><span class="dot"></span><span class="label"></span></div>
            <div class="sub"></div>
          </div>
          <div class="bar hidden"><div></div></div>
          <div class="actions">
            <button class="wake primary" hidden><ha-icon icon="mdi:alarm"></ha-icon>Wake</button>
            <button class="power"><ha-icon icon="mdi:power"></ha-icon><span></span></button>
          </div>
        </div>
      </ha-card>`;

    const $ = (s) => this.shadowRoot.querySelector(s);
    this._root = $(".root");
    this._img = $("img");
    this._name = $(".name");
    this._label = $(".label");
    this._sub = $(".sub");
    this._bar = $(".bar");
    this._barFill = $(".bar > div");
    this._wakeBtn = $(".wake");
    this._powerBtn = $(".power");

    this._img.addEventListener("error", () => {
      if (this._img.src !== FALLBACK_IMAGE) this._img.src = FALLBACK_IMAGE;
    });
    $(".hero").addEventListener("click", () => this._moreInfo());
    this._wakeBtn.addEventListener("click", () => this._wake());
    this._powerBtn.addEventListener("click", () => this._togglePower());
  }

  get _stateObj() {
    return this._hass?.states[this._config.entity];
  }

  _sibling(domain) {
    const ents = this._hass?.entities || {};
    const device = ents[this._config.entity]?.device_id;
    if (!device) return undefined;
    return Object.values(ents).find(
      (e) => e.device_id === device && e.entity_id.startsWith(`${domain}.`)
    )?.entity_id;
  }

  get _wakeEntity() {
    return this._sibling("button");
  }

  // The integration's Power switch; falls back to the raw plug on older versions.
  get _powerEntity() {
    return this._sibling("switch") || this._stateObj?.attributes?.plug_entity;
  }

  _update() {
    const st = this._stateObj;
    const state = st && STATES[st.state] ? st.state : "unavailable";
    this._root.className = `root ${state}`;

    const img = this._config.image || FALLBACK_IMAGE;
    if (this._img.getAttribute("src") !== img) this._img.setAttribute("src", img);

    this._name.textContent =
      this._config.name || this._hass.devices?.[this._hass.entities?.[this._config.entity]?.device_id]?.name ||
      st?.attributes?.friendly_name || "Coffee machine";
    this._label.textContent = STATES[state].label;

    const power = this._powerEntity;
    const powerState = power && this._hass.states[power]?.state;
    this._powerBtn.hidden = !this._config.show_power || !power;
    this._powerBtn.querySelector("span").textContent = powerState === "on" ? "Turn off" : "Turn on";
    this._powerBtn.classList.toggle("primary", state === "off");
    this._powerBtn.disabled = state === "waking" || !powerState || powerState === "unavailable";

    this._wakeBtn.hidden = state !== "sleeping";
    this._updateTime();
  }

  _updateTime() {
    const st = this._stateObj;
    if (!st || !this._sub) return;
    const now = Date.now();
    const heatingSince = st.attributes.heating_since ? Date.parse(st.attributes.heating_since) : null;
    const readySince = st.attributes.ready_since ? Date.parse(st.attributes.ready_since) : null;
    const sleepAt = st.attributes.sleep_at ? Date.parse(st.attributes.sleep_at) : null;

    let sub = STATES[st.state]?.sub ?? STATES.unavailable.sub;
    if (st.state === "heating") sub = heatingSince ? `Heating for ${fmt(now - heatingSince)}` : "Heating";
    if (st.state === "ready") sub = sleepAt ? `Sleeps in ${fmt(sleepAt - now)}` : "Up to temperature";
    this._sub.textContent = sub;

    // Countdown bar only while ready (the timer is paused while heating).
    if (st.state === "ready" && readySince && sleepAt && sleepAt > readySince) {
      const remaining = Math.min(1, Math.max(0, (sleepAt - now) / (sleepAt - readySince)));
      this._bar.classList.remove("hidden");
      this._barFill.style.width = `${remaining * 100}%`;
    } else {
      this._bar.classList.add("hidden");
    }
  }

  _wake() {
    const button = this._wakeEntity;
    if (button) this._hass.callService("button", "press", { entity_id: button });
  }

  _togglePower() {
    const power = this._powerEntity;
    if (!power) return;
    const on = this._hass.states[power]?.state === "on";
    this._hass.callService("homeassistant", on ? "turn_off" : "turn_on", { entity_id: power });
  }

  _moreInfo() {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId: this._config.entity },
        bubbles: true,
        composed: true,
      })
    );
  }
}

const EDITOR_SCHEMA = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: { integration: "coffee_machine", domain: "sensor", device_class: "enum" } } },
  },
  { name: "name", selector: { text: {} } },
  { name: "image", selector: { text: {} } },
  { name: "show_power", selector: { boolean: {} } },
];

const EDITOR_LABELS = {
  entity: "Coffee machine (Status entity)",
  name: "Name (optional)",
  image: "Image URL (optional)",
  show_power: "Show power (on/off) button",
};

const EDITOR_HELP = {
  image: "Put your photo in config/www/coffee/ and use /local/coffee/your-photo.png. A transparent PNG looks best.",
};

class CoffeeMachineCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { show_power: true, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => EDITOR_LABELS[s.name] ?? s.name;
      this._form.computeHelper = (s) => EDITOR_HELP[s.name];
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = EDITOR_SCHEMA;
  }
}

if (!customElements.get("coffee-machine-card")) {
  customElements.define("coffee-machine-card", CoffeeMachineCard);
  customElements.define("coffee-machine-card-editor", CoffeeMachineCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "coffee-machine-card",
    name: "Coffee Machine",
    description: "Shows your coffee machine's state with a photo, sleep countdown and a Wake button.",
    preview: true,
  });
  console.info(`%c COFFEE-MACHINE-CARD %c ${CARD_VERSION} `, "background:#6d4c41;color:#fff", "");
}
