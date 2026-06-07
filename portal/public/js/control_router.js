import { fetchMe, getToken } from "./control_api.js";
import { initBootstrap, teardownBootstrap } from "./control_bootstrap.js";
import { initDevicesSection, teardownDevicesSection } from "./control_devices.js";
import { initAclSection, teardownAclSection } from "./control_acl.js";

let _currentSub = null;
let _me = null;

export async function initControlSubroute(sub) {
  teardownAll();
  if (!getToken()) {
    await initBootstrap();
    _currentSub = "bootstrap";
    return;
  }
  try {
    _me = await fetchMe();
  } catch (e) {
    if (e.status === 401) {
      await initBootstrap();
      _currentSub = "bootstrap";
      return;
    }
    const view = document.getElementById("control-view");
    if (view) view.innerHTML = `<div class="control-error">Error: ${e.message}</div>`;
    _currentSub = "error";
    return;
  }

  const target = sub || "devices";
  if (target === "acl") {
    await initAclSection(_me);
    _currentSub = "acl";
  } else {
    await initDevicesSection(_me);
    _currentSub = "devices";
  }
}

export function teardownControlSubroute() {
  teardownAll();
}

function teardownAll() {
  if (_currentSub === "bootstrap") teardownBootstrap();
  else if (_currentSub === "devices") teardownDevicesSection();
  else if (_currentSub === "acl") teardownAclSection();
  _currentSub = null;
}

export function getCurrentControlSub() {
  return _currentSub;
}
