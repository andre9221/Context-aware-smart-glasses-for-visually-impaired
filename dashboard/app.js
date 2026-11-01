/**
 * Context-Aware Smart Glasses - Caregiver & Researcher Web Dashboard
 *
 * Implements:
 * 1. Role-Based Login Authentication (Researcher / Caregiver / Admin)
 * 2. 180° Top-Down Spatial Radar with Kinematic Head Yaw needle
 * 3. 3-Axis Neckband LRA Pulse Visualizer (Left, Center, Right)
 * 4. Live Rolling Hazard Detection Stream Table
 * 5. Chart.js Analytics (Hazard Donut + TTC Timeline)
 * 6. 1-Click Research Dataset Export (CSV / JSON)
 * 7. Authenticated Telemetry Receiver (SSE with session token)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM References - Auth
  const loginOverlay = document.getElementById("loginModalOverlay");
  const loginForm = document.getElementById("loginForm");
  const inputUsername = document.getElementById("inputUsername");
  const inputPassword = document.getElementById("inputPassword");
  const btnTogglePwd = document.getElementById("btnTogglePwd");
  const loginErrorMessage = document.getElementById("loginErrorMessage");
  const btnLoginSubmit = document.getElementById("btnLoginSubmit");
  const loginBtnText = document.getElementById("loginBtnText");
  const loginSpinner = document.getElementById("loginSpinner");

  const btnQuickPatient = document.getElementById("btnQuickPatient");
  const btnQuickDoctor = document.getElementById("btnQuickDoctor");
  const btnQuickCaregiver = document.getElementById("btnQuickCaregiver");

  const mainDashboardApp = document.getElementById("mainDashboardApp");
  const userProfileBadge = document.getElementById("userProfileBadge");
  const userAvatar = document.getElementById("userAvatar");
  const userName = document.getElementById("userName");
  const userRole = document.getElementById("userRole");
  const btnLogout = document.getElementById("btnLogout");
  const caregiverPortal = document.getElementById("caregiverPortal");
  const doctorPortal = document.getElementById("doctorPortal");
  const patientPortal = document.getElementById("patientPortal");
  const carePageTitle = document.getElementById("carePageTitle");
  const careClock = document.getElementById("careClock");
  const caregiverTitles = { dashboard: "Dashboard", camera: "Live POV Camera (Pi Cam 3)", gps: "GPS Location", traffic: "Traffic & Safety", wifi: "Glasses WiFi Data", reports: "Patient Reports" };

  function activateCarePage(page) {
    document.querySelectorAll(".care-page").forEach((view) => view.classList.toggle("active", view.dataset.view === page));
    document.querySelectorAll(".care-nav-item").forEach((item) => item.classList.toggle("active", item.dataset.page === page));
    if (carePageTitle) carePageTitle.textContent = caregiverTitles[page] || "Dashboard";
    document.querySelector(".care-sidebar")?.classList.remove("open");
    if (page === "camera") {
      initGuardianCamera();
    }
  }

  const doctorTitles = { dashboard: "Dashboard", preview: "Patient Preview", data: "Patient Data", history: "Previous Data", appointments: "Appointments", reports: "Reports & Prescriptions", summary: "Patient Summary" };
  function activateDoctorPage(page) {
    document.querySelectorAll("[data-doctor-view]").forEach((view) => {
      const isActive = view.dataset.doctorView === page;
      view.classList.toggle("active", isActive);
      view.style.display = isActive ? "flex" : "none";
    });
    document.querySelectorAll("[data-doctor-page]").forEach((item) => item.classList.toggle("active", item.dataset.doctorPage === page));
    const title = document.getElementById("doctorPageTitle");
    if (title) title.textContent = doctorTitles[page] || "Dashboard";
    document.querySelector(".doctor-portal .care-sidebar")?.classList.remove("open");
  }

  document.querySelectorAll("[data-doctor-page]").forEach((item) => item.addEventListener("click", () => activateDoctorPage(item.dataset.doctorPage)));
  document.getElementById("doctorMenuToggle")?.addEventListener("click", () => document.querySelector(".doctor-portal .care-sidebar")?.classList.toggle("open"));
  document.getElementById("doctorLogout")?.addEventListener("click", () => btnLogout.click());
  const doctorClock = document.getElementById("doctorClock");
  const updateDoctorClock = () => { if (doctorClock) doctorClock.textContent = new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date()); };
  updateDoctorClock();
  setInterval(updateDoctorClock, 1000);

  // Doctor notification menu
  const doctorNotificationsButton = document.getElementById("doctorNotificationsButton");
  const doctorNotifications = document.getElementById("doctorNotifications");
  const doctorNotificationCount = document.getElementById("doctorNotificationCount");
  const doctorNotificationItems = Array.from(document.querySelectorAll("[data-doctor-notification]"));
  const updateDoctorNotificationCount = () => {
    const unreadCount = doctorNotificationItems.filter((item) => item.dataset.unread === "true").length;
    if (doctorNotificationCount) {
      doctorNotificationCount.textContent = String(unreadCount);
      doctorNotificationCount.hidden = unreadCount === 0;
    }
    doctorNotificationsButton?.setAttribute("aria-label", `Notifications, ${unreadCount} unread`);
  };
  const closeDoctorNotifications = () => {
    if (!doctorNotifications || !doctorNotificationsButton) return;
    doctorNotifications.hidden = true;
    doctorNotificationsButton.setAttribute("aria-expanded", "false");
  };

  doctorNotificationsButton?.addEventListener("click", () => {
    if (!doctorNotifications) return;
    const opening = doctorNotifications.hidden;
    doctorNotifications.hidden = !opening;
    doctorNotificationsButton.setAttribute("aria-expanded", String(opening));
  });

  document.getElementById("markDoctorNotificationsRead")?.addEventListener("click", () => {
    doctorNotificationItems.forEach((item) => {
      item.dataset.unread = "false";
      item.classList.remove("is-unread");
    });
    updateDoctorNotificationCount();
  });

  doctorNotificationItems.forEach((item) => {
    item.addEventListener("click", () => {
      item.dataset.unread = "false";
      item.classList.remove("is-unread");
      updateDoctorNotificationCount();
      closeDoctorNotifications();
      if (item.dataset.page) activateDoctorPage(item.dataset.page);
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (event.target instanceof Element && !event.target.closest(".doctor-notification-wrap")) {
      closeDoctorNotifications();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDoctorNotifications();
  });
  updateDoctorNotificationCount();

  const patientTitles = { dashboard: "Dashboard", sync: "Glasses Sync", reports: "My Reports", appointments: "Appointments", medications: "Medications", reminders: "Reminders" };
  function activatePatientPage(page) {
    document.querySelectorAll("[data-patient-view]").forEach((view) => {
      const isActive = view.dataset.patientView === page;
      view.classList.toggle("active", isActive);
      view.style.display = isActive ? "flex" : "none";
    });
    document.querySelectorAll("[data-patient-page]").forEach((item) => item.classList.toggle("active", item.dataset.patientPage === page));
    const title = document.getElementById("patientPageTitle");
    if (title) title.textContent = patientTitles[page] || "Dashboard";
    document.querySelector(".patient-portal .care-sidebar")?.classList.remove("open");
  }
  document.querySelectorAll("[data-patient-page]").forEach((item) => item.addEventListener("click", () => activatePatientPage(item.dataset.patientPage)));
  document.getElementById("patientMenuToggle")?.addEventListener("click", () => document.querySelector(".patient-portal .care-sidebar")?.classList.toggle("open"));
  document.getElementById("patientLogout")?.addEventListener("click", () => btnLogout.click());
  const patientClock = document.getElementById("patientClock");
  const updatePatientClock = () => { if (patientClock) patientClock.textContent = new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date()); };
  updatePatientClock();
  setInterval(updatePatientClock, 1000);
  const patientNotificationsButton = document.getElementById("patientNotificationsButton");
  const patientNotifications = document.getElementById("patientNotifications");
  patientNotificationsButton?.addEventListener("click", () => {
    const opening = patientNotifications.hidden;
    patientNotifications.hidden = !opening;
    patientNotificationsButton.setAttribute("aria-expanded", String(opening));
  });
  const closePatientNotifications = () => {
    if (!patientNotifications || !patientNotificationsButton) return;
    patientNotifications.hidden = true;
    patientNotificationsButton.setAttribute("aria-expanded", "false");
  };
  document.getElementById("clearPatientNotifications")?.addEventListener("click", () => {
    document.getElementById("patientNotificationList").replaceChildren();
    const count = document.getElementById("patientNotificationCount");
    count.textContent = "0";
    count.hidden = true;
  });
  document.addEventListener("pointerdown", (event) => {
    if (event.target instanceof Element && !event.target.closest(".patient-notification-wrap")) closePatientNotifications();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePatientNotifications();
  });
  document.getElementById("patientForceSync")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const state = document.getElementById("patientSyncState");
    button.disabled = true;
    button.textContent = "⟳  Syncing…";
    state.textContent = "Syncing";
    window.setTimeout(() => {
      document.getElementById("patientLastSync").textContent = new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
      state.textContent = "Synced";
      button.disabled = false;
      button.textContent = "⟳  Force Sync";
    }, 900);
  });

  document.querySelectorAll(".patient-row").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("[data-open-patient]") || event.target.closest(".patient-info")) {
        const patientName = row.dataset.patient || "Alex Rivera";
        document.querySelectorAll(".selected-patient-name").forEach((node) => { node.textContent = patientName; });
        document.querySelectorAll(".patient-row").forEach((patient) => patient.classList.toggle("selected", patient === row));
        activateDoctorPage("data");
      }
    });
  });
  document.querySelectorAll('[data-doctor-action="print"]').forEach((button) => button.addEventListener("click", () => window.print()));
  document.querySelectorAll('[data-doctor-action="export"], [data-doctor-action="export-all"]').forEach((button) => button.addEventListener("click", () => {
    const rows = Array.from(document.querySelectorAll('[data-doctor-view="reports"] .care-table tr'));
    const csv = rows.map((row) => Array.from(row.cells).map((cell) => `"${cell.innerText.replaceAll('"', '""')}"`).join(",")).join("\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = "visioncare-clinical-reports.csv"; link.click(); URL.revokeObjectURL(link.href);
  }));
  document.querySelector('[data-doctor-action="search"]')?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const term = window.prompt("Search patient names");
    if (term === null) return;
    const query = term.trim().toLowerCase();
    document.querySelectorAll(".patient-row").forEach((row) => { row.hidden = query.length > 0 && !row.innerText.toLowerCase().includes(query); });
    button.textContent = query ? `⌕ ${query} · clear` : "⌕  Search";
  });
  document.querySelector('[data-doctor-action="schedule"]')?.addEventListener("click", () => {
    const title = window.prompt("Appointment title");
    if (!title?.trim()) return;
    const article = document.createElement("article");
    article.innerHTML = `<span class="appointment-date"><strong>NEW</strong><small>DATE</small></span><div><h3></h3><p>Dr. Sarah Mitchell · To be confirmed · In-Person</p></div><b class="risk-tag info">Upcoming</b>`;
    article.querySelector("h3").textContent = title.trim();
    document.querySelector(".appointment-list")?.prepend(article);
  });

  document.querySelectorAll(".caregiver-portal .care-nav-item").forEach((item) => {
    item.addEventListener("click", () => activateCarePage(item.dataset.page));
  });
  document.getElementById("careMenuToggle")?.addEventListener("click", () => document.querySelector(".care-sidebar")?.classList.toggle("open"));
  document.getElementById("careLogout")?.addEventListener("click", () => btnLogout.click());
  const updateCareClock = () => {
    if (careClock) careClock.textContent = new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
  };
  updateCareClock();
  setInterval(updateCareClock, 1000);

  // Primary caregiver notification menu
  const careNotificationsButton = document.getElementById("careNotificationsButton");
  const careNotifications = document.getElementById("careNotifications");
  const careNotificationCount = document.getElementById("careNotificationCount");
  const careNotificationItems = Array.from(document.querySelectorAll("[data-care-notification]"));
  const updateCareNotificationCount = () => {
    const unreadCount = careNotificationItems.filter((item) => item.dataset.unread === "true").length;
    if (careNotificationCount) {
      careNotificationCount.textContent = String(unreadCount);
      careNotificationCount.hidden = unreadCount === 0;
    }
    careNotificationsButton?.setAttribute("aria-label", `Notifications, ${unreadCount} unread`);
  };
  const closeCareNotifications = () => {
    if (!careNotifications || !careNotificationsButton) return;
    careNotifications.hidden = true;
    careNotificationsButton.setAttribute("aria-expanded", "false");
  };
  careNotificationsButton?.addEventListener("click", () => {
    if (!careNotifications) return;
    const opening = careNotifications.hidden;
    careNotifications.hidden = !opening;
    careNotificationsButton.setAttribute("aria-expanded", String(opening));
  });
  document.getElementById("markCareNotificationsRead")?.addEventListener("click", () => {
    careNotificationItems.forEach((item) => {
      item.dataset.unread = "false";
      item.classList.remove("is-unread");
    });
    updateCareNotificationCount();
  });
  careNotificationItems.forEach((item) => {
    item.addEventListener("click", () => {
      item.dataset.unread = "false";
      item.classList.remove("is-unread");
      updateCareNotificationCount();
      closeCareNotifications();
      if (item.dataset.page) activateCarePage(item.dataset.page);
    });
  });
  document.addEventListener("pointerdown", (event) => {
    if (event.target instanceof Element && !event.target.closest(".doctor-notification-wrap")) closeCareNotifications();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCareNotifications();
  });
  updateCareNotificationCount();

  // DOM References - Dashboard
  const radarCanvas = document.getElementById("spatialRadarCanvas");
  const radarCtx = radarCanvas.getContext("2d");

  const headYawDisplay = document.getElementById("headYawDisplay");
  const criticalDistVal = document.getElementById("criticalDistVal");
  const interruptStateVal = document.getElementById("interruptStateVal");
  const computeSavingsVal = document.getElementById("computeSavingsVal");
  const systemLatency = document.getElementById("systemLatency");
  const sessionTimer = document.getElementById("sessionTimer");
  const eventCountBadge = document.getElementById("eventCountBadge");
  const eventTableBody = document.getElementById("eventTableBody");
  const urgencyPill = document.getElementById("urgencyPill");

  const nodeLeft = document.getElementById("nodeLeft");
  const nodeCenter = document.getElementById("nodeCenter");
  const nodeRight = document.getElementById("nodeRight");
  const stateLeft = document.getElementById("stateLeft");
  const stateCenter = document.getElementById("stateCenter");
  const stateRight = document.getElementById("stateRight");

  const activeWaveformName = document.getElementById("activeWaveformName");
  const firingCadence = document.getElementById("firingCadence");
  const ttcVal = document.getElementById("ttcVal");

  const btnExportCsv = document.getElementById("btnExportCsv");
  const btnExportJson = document.getElementById("btnExportJson");

  // State
  let authToken = localStorage.getItem("smart_glasses_token") || null;
  let currentUser = null;
  let sseEventSource = null;
  let sessionStartTime = Date.now();
  let eventsHistory = [];
  let classCounts = { person: 0, car: 0, truck: 0, overhead_hazard: 0, generic_obstacle: 0 };
  let currentHeadYaw = 0.0;
  let currentObstacle = { dist: 2.5, azimuth: 0, class: "person", active: false };

  // ============================================================================
  // AUTHENTICATION LOGIC & SESSION CHECK
  // ============================================================================
  async function checkExistingSession() {
    if (!authToken) {
      showLoginModal();
      return;
    }

    try {
      const res = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        handleLoginSuccess(authToken, data.user);
      } else {
        localStorage.removeItem("smart_glasses_token");
        authToken = null;
        showLoginModal();
      }
    } catch (err) {
      // If server is not responding to /api/auth/me directly, check local token
      const savedUser = localStorage.getItem("smart_glasses_user");
      if (savedUser) {
        try {
          handleLoginSuccess(authToken, JSON.parse(savedUser));
          return;
        } catch (e) {}
      }
      showLoginModal();
    }
  }

  function showLoginModal() {
    loginOverlay.classList.remove("hidden");
    mainDashboardApp.classList.add("blurred");
    if (sseEventSource) {
      sseEventSource.close();
      sseEventSource = null;
    }
  }

  function hideLoginModal() {
    loginOverlay.classList.add("hidden");
    mainDashboardApp.classList.remove("blurred");
  }

  function handleLoginSuccess(token, user) {
    authToken = token;
    currentUser = user;
    localStorage.setItem("smart_glasses_token", token);
    localStorage.setItem("smart_glasses_user", JSON.stringify(user));

    // Update Header Profile Badge
    userAvatar.textContent = user.avatar || "👤";
    userName.textContent = user.name || user.username;
    userRole.textContent = user.role || "User";

    const isCaregiver = (user.role || "").toLowerCase().includes("caregiver");
    const isDoctor = (user.role || "").toLowerCase().includes("doctor");
    const isPatient = (user.role || "").toLowerCase().includes("patient");
    const isResearcher = (user.role || "").toLowerCase().includes("researcher");
    const hasRolePortal = isCaregiver || isDoctor || isPatient;
    document.body.classList.toggle("caregiver-view", isCaregiver);
    document.body.classList.toggle("doctor-view", isDoctor);
    document.body.classList.toggle("patient-view", isPatient);
    document.body.classList.toggle("researcher-view", isResearcher);
    if (caregiverPortal) caregiverPortal.style.display = isCaregiver ? "flex" : "none";
    if (doctorPortal) doctorPortal.style.display = isDoctor ? "flex" : "none";
    if (patientPortal) patientPortal.style.display = isPatient ? "flex" : "none";
    document.querySelectorAll(".status-header, .dashboard-grid, .system-footer").forEach((section) => {
      section.style.display = hasRolePortal ? "none" : "";
    });
    if (isCaregiver) activateCarePage("dashboard");
    if (isDoctor) activateDoctorPage("dashboard");
    if (isPatient) activatePatientPage("dashboard");

    hideLoginModal();
    connectTelemetryStream();
  }

  // Password Visibility Toggle
  btnTogglePwd.addEventListener("click", () => {
    if (inputPassword.type === "password") {
      inputPassword.type = "text";
      btnTogglePwd.textContent = "🙈";
    } else {
      inputPassword.type = "password";
      btnTogglePwd.textContent = "👁️";
    }
  });

  // Perform Login Request
  async function performLogin(username, password) {
    loginErrorMessage.style.display = "none";
    loginBtnText.textContent = "Signing In...";
    btnLoginSubmit.disabled = true;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (res.ok && data.status === "ok") {
        handleLoginSuccess(data.token, data.user);
      } else {
        loginErrorMessage.textContent = data.detail || "Authentication failed. Check credentials.";
        loginErrorMessage.style.display = "flex";
      }
    } catch (err) {
      // Fallback offline mock authentication
      if (username === "researcher" && password === "Glasses2026!") {
        handleLoginSuccess("mock_res_token", {
          username: "researcher",
          name: "Lead Researcher",
          role: "Lead Researcher",
          avatar: "🔬",
        });
      } else if (username === "caregiver" && password === "Caregiver2026!") {
        handleLoginSuccess("mock_care_token", {
          username: "caregiver",
          name: "Primary Caregiver",
          role: "Primary Caregiver",
          avatar: "🩺",
        });
      } else if (username === "doctor" && password === "Doctor2026!") {
        handleLoginSuccess("mock_doctor_token", {
          username: "doctor",
          name: "Dr. Sarah Mitchell",
          role: "Doctor",
          avatar: "🩻",
        });
      } else if (username === "patient" && password === "Patient2026!") {
        handleLoginSuccess("mock_patient_token", { username: "patient", name: "Alex Rivera", role: "Patient", avatar: "AR" });
      } else {
        loginErrorMessage.textContent = "Invalid username or password.";
        loginErrorMessage.style.display = "flex";
      }
    } finally {
      loginBtnText.textContent = "Sign In to Dashboard";
      btnLoginSubmit.disabled = false;
    }
  }

  loginForm.addEventListener("submit", (e) => {
    e.preventDefault();
    performLogin(inputUsername.value, inputPassword.value);
  });

  // 1-Click Quick Demo Login Handlers
  btnQuickDoctor.addEventListener("click", () => {
    inputUsername.value = "doctor";
    inputPassword.value = "Doctor2026!";
    performLogin("doctor", "Doctor2026!");
  });

  btnQuickCaregiver.addEventListener("click", () => {
    inputUsername.value = "caregiver";
    inputPassword.value = "Caregiver2026!";
    performLogin("caregiver", "Caregiver2026!");
  });

  btnQuickPatient.addEventListener("click", () => {
    inputUsername.value = "patient";
    inputPassword.value = "Patient2026!";
    performLogin("patient", "Patient2026!");
  });

  // Logout Handler
  btnLogout.addEventListener("click", async () => {
    try {
      if (authToken) {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${authToken}` },
        });
      }
    } catch (e) {}

    localStorage.removeItem("smart_glasses_token");
    localStorage.removeItem("smart_glasses_user");
    authToken = null;
    currentUser = null;
    showLoginModal();
  });

  // ============================================================================
  // Session Timer
  // ============================================================================
  setInterval(() => {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const hrs = String(Math.floor(elapsed / 3600)).padStart(2, "0");
    const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
    const secs = String(elapsed % 60).padStart(2, "0");
    sessionTimer.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);

  // ============================================================================
  // Chart.js Setup
  // ============================================================================
  const ctxHazard = document.getElementById("hazardDistributionChart").getContext("2d");
  const hazardChart = new Chart(ctxHazard, {
    type: "doughnut",
    data: {
      labels: ["Pedestrian", "Vehicle", "Overhead", "Other"],
      datasets: [{
        data: [1, 1, 1, 1],
        backgroundColor: ["#10b981", "#ef4444", "#a855f7", "#3b82f6"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { color: "#9ca3af", font: { size: 10 } } },
      },
      cutout: "68%",
    },
  });

  const ctxTimeline = document.getElementById("ttcTimelineChart").getContext("2d");
  const timelineChart = new Chart(ctxTimeline, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "TTC (s)",
          data: [],
          borderColor: "#00f2fe",
          backgroundColor: "rgba(0, 242, 254, 0.1)",
          tension: 0.3,
          borderWidth: 2,
          yAxisID: "yTTC",
        },
        {
          label: "Dist (m)",
          data: [],
          borderColor: "#f59e0b",
          borderDash: [4, 4],
          tension: 0.3,
          borderWidth: 1.5,
          yAxisID: "yDist",
        }
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { display: false },
        yTTC: {
          position: "left",
          min: 0,
          max: 6,
          ticks: { color: "#00f2fe", font: { size: 9 } },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        yDist: {
          position: "right",
          min: 0,
          max: 4,
          ticks: { color: "#f59e0b", font: { size: 9 } },
          grid: { display: false },
        }
      },
      plugins: {
        legend: { labels: { color: "#9ca3af", font: { size: 10 } } },
      },
    },
  });

  // ============================================================================
  // 180° Spatial Radar Canvas Rendering
  // ============================================================================
  function drawRadar() {
    const w = radarCanvas.width;
    const h = radarCanvas.height;
    radarCtx.clearRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h - 25;
    const maxRadius = h - 45;

    // Draw range arc rings (1m, 2m, 3m, 4m)
    const ranges = [1, 2, 3, 4];
    radarCtx.lineWidth = 1;
    ranges.forEach((r) => {
      const radius = (r / 4.0) * maxRadius;
      radarCtx.beginPath();
      radarCtx.arc(cx, cy, radius, Math.PI, 2 * Math.PI, false);
      radarCtx.strokeStyle = r === 2 ? "rgba(239, 68, 68, 0.4)" : "rgba(255, 255, 255, 0.08)";
      if (r === 2) {
        radarCtx.setLineDash([4, 4]); // 2.0m interrupt gate ring
      } else {
        radarCtx.setLineDash([]);
      }
      radarCtx.stroke();

      radarCtx.fillStyle = r === 2 ? "#ef4444" : "rgba(255, 255, 255, 0.3)";
      radarCtx.font = "9px JetBrains Mono";
      radarCtx.fillText(`${r}m`, cx + radius - 15, cy - 4);
    });
    radarCtx.setLineDash([]);

    // Sector dividing lines
    const anglesDeg = [-45, -15, 15, 45];
    anglesDeg.forEach((deg) => {
      const rad = (deg - 90) * (Math.PI / 180.0);
      radarCtx.beginPath();
      radarCtx.moveTo(cx, cy);
      radarCtx.lineTo(cx + Math.cos(rad) * maxRadius, cy + Math.sin(rad) * maxRadius);
      radarCtx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      radarCtx.stroke();
    });

    // Draw Head Yaw Compass Needle
    const yawRad = (currentHeadYaw - 90) * (Math.PI / 180.0);
    radarCtx.beginPath();
    radarCtx.moveTo(cx, cy);
    radarCtx.lineTo(cx + Math.cos(yawRad) * (maxRadius * 0.95), cy + Math.sin(yawRad) * (maxRadius * 0.95));
    radarCtx.strokeStyle = "#00f2fe";
    radarCtx.lineWidth = 2;
    radarCtx.shadowColor = "#00f2fe";
    radarCtx.shadowBlur = 8;
    radarCtx.stroke();
    radarCtx.shadowBlur = 0;

    // Torso mark
    radarCtx.beginPath();
    radarCtx.arc(cx, cy, 7, 0, 2 * Math.PI);
    radarCtx.fillStyle = "#10b981";
    radarCtx.fill();

    // Active obstacle blip
    if (currentObstacle.active && currentObstacle.dist <= 4.0) {
      const blipRad = (currentObstacle.azimuth - 90) * (Math.PI / 180.0);
      const blipDistPx = (currentObstacle.dist / 4.0) * maxRadius;
      const bx = cx + Math.cos(blipRad) * blipDistPx;
      const by = cy + Math.sin(blipRad) * blipDistPx;

      radarCtx.beginPath();
      radarCtx.arc(bx, by, 10, 0, 2 * Math.PI);
      radarCtx.fillStyle = currentObstacle.dist < 1.0 ? "rgba(239, 68, 68, 0.4)" : "rgba(245, 158, 11, 0.35)";
      radarCtx.fill();

      radarCtx.beginPath();
      radarCtx.arc(bx, by, 5, 0, 2 * Math.PI);
      radarCtx.fillStyle = currentObstacle.dist < 1.0 ? "#ef4444" : "#f59e0b";
      radarCtx.fill();

      radarCtx.fillStyle = "#ffffff";
      radarCtx.font = "10px Outfit";
      radarCtx.fillText(`${currentObstacle.dist.toFixed(1)}m (${currentObstacle.class})`, bx + 8, by - 4);
    }
  }

  // ============================================================================
  // Telemetry Packet Ingestion & UI Update
  // ============================================================================
  function handleTelemetryEvent(event) {
    eventsHistory.push(event);
    if (eventsHistory.length > 500) eventsHistory.shift();

    systemLatency.textContent = `${(event.latency_ms || 18.4).toFixed(1)} ms`;
    eventCountBadge.textContent = `${eventsHistory.length} Events`;

    currentHeadYaw = event.head_yaw_deg || 0.0;
    headYawDisplay.textContent = `${currentHeadYaw >= 0 ? "+" : ""}${currentHeadYaw.toFixed(1)}°`;

    let azAngle = 0;
    if (event.motor_channel === "LEFT") azAngle = -30;
    else if (event.motor_channel === "RIGHT") azAngle = 30;

    currentObstacle = {
      dist: event.distance_m || 4.0,
      azimuth: azAngle,
      class: event.hazard_class || "person",
      active: event.is_depth_interrupt || false,
    };
    drawRadar();

    criticalDistVal.textContent = `${(event.distance_m || 4.0).toFixed(2)} m`;
    interruptStateVal.textContent = event.is_depth_interrupt ? "TRIGGERED (<2m)" : "IDLE (>2m)";
    interruptStateVal.style.color = event.is_depth_interrupt ? "#ef4444" : "#10b981";

    const savings = event.roi_area_ratio > 0 ? (1.0 - event.roi_area_ratio) * 100 : (event.ai_gated ? 100 : 85);
    computeSavingsVal.textContent = `${savings.toFixed(1)}%`;

    activeWaveformName.textContent = `${event.waveform_name || "Strong Click - 100%"} (#${event.waveform_id || 1})`;
    ttcVal.textContent = event.ttc_seconds < 90 ? `${event.ttc_seconds.toFixed(2)} s` : "> 10 s";

    urgencyPill.textContent = event.urgency_level || "SAFE";
    urgencyPill.className = `badge-pill ${event.urgency_level ? event.urgency_level.toLowerCase() : "safe"}`;

    if (event.urgency_level === "IMMINENT") {
      firingCadence.textContent = "20 Hz (Continuous Rapid Buzz)";
    } else if (event.urgency_level === "APPROACHING") {
      firingCadence.textContent = "4.0 Hz (Double-Pulse Cadence)";
    } else {
      firingCadence.textContent = "1.0 Hz (Gentle Situational Ping)";
    }

    triggerNodePulse(event.motor_channel, event.urgency_level, event.should_pulse);
    appendTableRow(event);
    updateCharts(event);

    // Update new Guardian Camera Feed & Patient ToF Dashboard
    updateGuardianCameraTelemetry(event);
    updatePatientTofTelemetry(event);
  }

  function triggerNodePulse(channel, urgency, shouldPulse) {
    const nodes = { LEFT: nodeLeft, CENTER: nodeCenter, RIGHT: nodeRight };
    const states = { LEFT: stateLeft, CENTER: stateCenter, RIGHT: stateRight };

    ["LEFT", "CENTER", "RIGHT"].forEach((ch) => {
      nodes[ch].className = "lra-node";
      states[ch].textContent = "IDLE";
      states[ch].style.color = "var(--text-muted)";
    });

    if (channel && shouldPulse && nodes[channel]) {
      const pulseClass = urgency === "IMMINENT" ? "pulsing-red" : (urgency === "APPROACHING" ? "pulsing-yellow" : "pulsing-green");
      nodes[channel].classList.add(pulseClass);
      states[channel].textContent = urgency === "IMMINENT" ? "BUZZING!" : "PULSING";
      states[channel].style.color = urgency === "IMMINENT" ? "#ef4444" : (urgency === "APPROACHING" ? "#f59e0b" : "#10b981");

      setTimeout(() => {
        nodes[channel].classList.remove(pulseClass);
        states[channel].textContent = "IDLE";
        states[channel].style.color = "var(--text-muted)";
      }, 240);
    }
  }

  function appendTableRow(event) {
    const row = document.createElement("tr");
    const d = new Date(event.timestamp * 1000);
    const timeStr = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;

    const hClass = (event.hazard_class || "person").toLowerCase();
    let tagStyle = "tag-person";
    if (["car", "truck", "bus"].includes(hClass)) tagStyle = "tag-car";
    else if (hClass.includes("overhead")) tagStyle = "tag-overhead";

    row.innerHTML = `
      <td>${timeStr}</td>
      <td><span class="tag-class ${tagStyle}">${hClass}</span></td>
      <td><strong>${event.motor_channel || "CENTER"}</strong></td>
      <td>${(event.distance_m || 4.0).toFixed(2)}m</td>
      <td>${event.ttc_seconds < 90 ? event.ttc_seconds.toFixed(2) + "s" : "--"}</td>
      <td>#${event.waveform_id || 1}</td>
      <td>${event.urgency_level || "SAFE"}</td>
    `;

    eventTableBody.insertBefore(row, eventTableBody.firstChild);
    while (eventTableBody.children.length > 30) {
      eventTableBody.removeChild(eventTableBody.lastChild);
    }
  }

  function updateCharts(event) {
    const hClass = (event.hazard_class || "person").toLowerCase();
    if (["person", "pedestrian"].includes(hClass)) classCounts.person++;
    else if (["car", "bus", "truck", "motorcycle"].includes(hClass)) classCounts.car++;
    else if (hClass.includes("overhead")) classCounts.overhead_hazard++;
    else classCounts.generic_obstacle++;

    hazardChart.data.datasets[0].data = [
      classCounts.person,
      classCounts.car,
      classCounts.overhead_hazard,
      classCounts.generic_obstacle,
    ];
    hazardChart.update("none");

    if (timelineChart.data.labels.length > 20) {
      timelineChart.data.labels.shift();
      timelineChart.data.datasets[0].data.shift();
      timelineChart.data.datasets[1].data.shift();
    }
    const d = new Date(event.timestamp * 1000);
    timelineChart.data.labels.push(`${d.getSeconds()}s`);
    timelineChart.data.datasets[0].data.push(event.ttc_seconds < 10 ? event.ttc_seconds : 6);
    timelineChart.data.datasets[1].data.push(event.distance_m || 4.0);
    timelineChart.update("none");
  }

  // ============================================================================
  // 1-Click Research Dataset Export
  // ============================================================================
  btnExportCsv.addEventListener("click", () => {
    if (eventsHistory.length === 0) {
      alert("No telemetry events recorded yet.");
      return;
    }
    const headers = ["timestamp", "head_yaw_deg", "motor_channel", "distance_m", "ttc_seconds", "urgency_level", "hazard_class", "waveform_id", "waveform_name", "roi_area_ratio", "latency_ms"];
    let csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n";
    eventsHistory.forEach((e) => {
      const row = [
        e.timestamp,
        e.head_yaw_deg,
        e.motor_channel,
        e.distance_m,
        e.ttc_seconds,
        e.urgency_level,
        e.hazard_class,
        e.waveform_id,
        `"${e.waveform_name}"`,
        e.roi_area_ratio,
        e.latency_ms,
      ];
      csvContent += row.join(",") + "\n";
    });
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `smart_glasses_trials_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  btnExportJson.addEventListener("click", () => {
    if (eventsHistory.length === 0) {
      alert("No telemetry events recorded yet.");
      return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(eventsHistory, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", dataStr);
    link.setAttribute("download", `smart_glasses_session_${Date.now()}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // ============================================================================
  // Authenticated Telemetry Receiver
  // ============================================================================
  function connectTelemetryStream() {
    if (!authToken) return;

    if (sseEventSource) {
      sseEventSource.close();
      sseEventSource = null;
    }

    try {
      sseEventSource = new EventSource(`/api/stream?token=${encodeURIComponent(authToken)}`);
      sseEventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          handleTelemetryEvent(data);
        } catch (err) {}
      };
      sseEventSource.onerror = () => {
        sseEventSource.close();
        // Fallback to active mock simulation if backend stream is quiet
        startFallbackSimulationLoop();
      };
    } catch (e) {
      startFallbackSimulationLoop();
    }
  }

  function startFallbackSimulationLoop() {
    console.log("[Dashboard] Fallback simulation loop disabled. Waiting for real webcam data.");
  }

  // ============================================================================
  // GUARDIAN CAMERA DASHBOARD (Pi Camera Module 3 - Sony IMX708 AF)
  // ============================================================================
  let guardianCamInitialized = false;
  let aiOverlayEnabled = true;
  let privacyShutterActive = false;
  let nightBoostActive = false;
  let lastCameraEvent = null;

  function initGuardianCamera() {
    if (guardianCamInitialized) return;
    guardianCamInitialized = true;

    // View Full POV button on caregiver overview card
    document.getElementById("btnOpenFullCamera")?.addEventListener("click", () => activateCarePage("camera"));
    document.querySelectorAll("[data-go-camera]").forEach((btn) => {
      btn.addEventListener("click", () => activateCarePage("camera"));
    });

    const overlayCanvas = document.getElementById("cameraOverlayCanvas");
    const streamImg = document.getElementById("guardianMainStreamImg");
    const aiStateLabel = document.getElementById("aiOverlayState");
    const privacyOverlay = document.getElementById("privacyOverlay");

    // Snapshot Capture
    document.getElementById("btnCamSnapshot")?.addEventListener("click", () => {
      captureCameraSnapshot();
    });

    // Toggle AI Bounding Boxes
    document.getElementById("btnToggleAiOverlay")?.addEventListener("click", () => {
      aiOverlayEnabled = !aiOverlayEnabled;
      if (aiStateLabel) aiStateLabel.textContent = aiOverlayEnabled ? "ON" : "OFF";
      if (!aiOverlayEnabled && overlayCanvas) {
        const ctx = overlayCanvas.getContext("2d");
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      }
    });

    // Privacy Shutter
    const togglePrivacy = (paused) => {
      privacyShutterActive = paused;
      if (privacyOverlay) privacyOverlay.style.display = paused ? "flex" : "none";
      if (streamImg) streamImg.style.opacity = paused ? "0.05" : "1";
    };

    document.getElementById("btnTogglePrivacy")?.addEventListener("click", () => {
      togglePrivacy(!privacyShutterActive);
    });

    document.getElementById("btnResumeStream")?.addEventListener("click", () => {
      togglePrivacy(false);
    });

    // Low-Light Boost
    document.getElementById("btnNightBoost")?.addEventListener("click", (e) => {
      nightBoostActive = !nightBoostActive;
      const target = e.currentTarget;
      if (target) target.classList.toggle("active-tool", nightBoostActive);
      if (streamImg) streamImg.classList.toggle("night-boost-filter", nightBoostActive);
    });

    // Audio Ping Patient
    document.getElementById("btnTriggerAudioPing")?.addEventListener("click", () => {
      alert("Sent audio ping to patient glasses! Neckband haptic alerted.");
    });

    // Fullscreen
    document.getElementById("btnFullscreenCam")?.addEventListener("click", () => {
      const feed = document.getElementById("cameraFeedContainer");
      if (feed) {
        if (!document.fullscreenElement) {
          feed.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      }
    });
  }

  function captureCameraSnapshot() {
    const streamImg = document.getElementById("guardianMainStreamImg");
    const gallery = document.getElementById("snapshotGallery");
    if (!streamImg) return;

    try {
      const snapCanvas = document.createElement("canvas");
      snapCanvas.width = streamImg.naturalWidth || 640;
      snapCanvas.height = streamImg.naturalHeight || 480;
      const ctx = snapCanvas.getContext("2d");
      ctx.drawImage(streamImg, 0, 0, snapCanvas.width, snapCanvas.height);

      // Add timestamp & camera stamp
      ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
      ctx.fillRect(0, snapCanvas.height - 35, snapCanvas.width, 35);
      ctx.fillStyle = "#10b981";
      ctx.font = "bold 13px 'JetBrains Mono', monospace";
      const nowStr = new Intl.DateTimeFormat([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
      ctx.fillText(`PI CAM 3 (IMX708) · ${nowStr} · LAT: 12.9715°N, 77.5945°E`, 15, snapCanvas.height - 12);

      const dataUrl = snapCanvas.toDataURL("image/jpeg", 0.9);

      // Create snapshot thumbnail card in gallery
      if (gallery) {
        const emptyNote = gallery.querySelector(".empty-note");
        if (emptyNote) emptyNote.remove();

        const item = document.createElement("article");
        item.className = "snapshot-item";
        item.innerHTML = `
          <img src="${dataUrl}" alt="Snapshot ${nowStr}">
          <div class="snap-meta">
            <span>${nowStr}</span>
            <a href="${dataUrl}" download="glasses_cam3_snap_${Date.now()}.jpg" class="snap-dl" title="Download Image">⬇ Save</a>
          </div>
        `;
        gallery.prepend(item);
      }
    } catch (err) {
      console.warn("[Camera Snapshot] Cross-origin or capture restriction:", err);
      // Fallback: trigger download link directly from backend endpoint if available
      window.open("/api/video_feed", "_blank");
    }
  }

  function updateGuardianCameraTelemetry(event) {
    lastCameraEvent = event;

    // Update latency & FPS pill
    const latencyPill = document.getElementById("camLatencyPill");
    if (latencyPill) latencyPill.textContent = `Latency: ${(event.latency_ms || 32).toFixed(0)}ms`;

    const fpsPill = document.getElementById("camFpsPill");
    if (fpsPill) fpsPill.textContent = "30 FPS";

    const ttcPill = document.getElementById("camTtcPill");
    if (ttcPill) {
      const ttc = event.ttc_seconds || 99;
      if (ttc < 1.5) {
        ttcPill.textContent = `TTC: CRITICAL (${ttc.toFixed(1)}s)`;
        ttcPill.className = "hud-pill hud-danger";
      } else if (ttc < 3.5) {
        ttcPill.textContent = `TTC: Approaching (${ttc.toFixed(1)}s)`;
        ttcPill.className = "hud-pill hud-warning";
      } else {
        ttcPill.textContent = `TTC: Safe (>4.0s)`;
        ttcPill.className = "hud-pill";
      }
    }

    // Update preview card in Caregiver Dashboard
    const previewBox = document.getElementById("guardianHudBox");
    const previewLabel = document.getElementById("guardianHudLabel");
    const previewStatus = document.getElementById("guardianPreviewStatus");

    if (event.is_depth_interrupt) {
      if (previewBox) previewBox.style.display = "block";
      if (previewLabel) previewLabel.textContent = `${event.hazard_class || "Obstacle"} ${(event.distance_m || 1.2).toFixed(1)}m`;
      if (previewStatus) {
        previewStatus.textContent = `Hazard: ${event.motor_channel || "Center"}`;
        previewStatus.className = "red-text";
      }
    } else {
      if (previewBox) previewBox.style.display = "none";
      if (previewStatus) {
        previewStatus.textContent = "Path Clear";
        previewStatus.className = "green-text";
      }
    }

    // Draw dynamic AI ROI box on overlay canvas
    const overlayCanvas = document.getElementById("cameraOverlayCanvas");
    if (overlayCanvas && aiOverlayEnabled && !privacyShutterActive) {
      const container = overlayCanvas.parentElement;
      if (container && (overlayCanvas.width !== container.clientWidth || overlayCanvas.height !== container.clientHeight)) {
        overlayCanvas.width = container.clientWidth;
        overlayCanvas.height = container.clientHeight;
      }

      const ctx = overlayCanvas.getContext("2d");
      ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

      if (event.is_depth_interrupt && event.distance_m < 2.5) {
        const cw = overlayCanvas.width;
        const ch = overlayCanvas.height;

        let bx = cw * 0.35;
        let bw = cw * 0.30;
        if (event.motor_channel === "LEFT") bx = cw * 0.12;
        else if (event.motor_channel === "RIGHT") bx = cw * 0.58;

        const by = ch * 0.22;
        const bh = ch * 0.55;

        // Draw bounding rectangle
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = event.distance_m < 1.0 ? "#ef4444" : "#f59e0b";
        ctx.strokeRect(bx, by, bw, bh);

        // Corner accents
        const cornerLen = 14;
        ctx.fillStyle = ctx.strokeStyle;
        ctx.fillRect(bx, by, cornerLen, 3);
        ctx.fillRect(bx, by, 3, cornerLen);
        ctx.fillRect(bx + bw - cornerLen, by, cornerLen, 3);
        ctx.fillRect(bx + bw - 3, by, 3, cornerLen);
        ctx.fillRect(bx, by + bh - 3, cornerLen, 3);
        ctx.fillRect(bx, by + bh - cornerLen, 3, cornerLen);
        ctx.fillRect(bx + bw - cornerLen, by + bh - 3, cornerLen, 3);
        ctx.fillRect(bx + bw - 3, by + bh - cornerLen, 3, cornerLen);

        // Label banner
        ctx.fillStyle = event.distance_m < 1.0 ? "rgba(239, 68, 68, 0.85)" : "rgba(245, 158, 11, 0.85)";
        const labelText = ` ${event.hazard_class ? event.hazard_class.toUpperCase() : "OBSTACLE"} | ${(event.distance_m || 1.2).toFixed(2)}m `;
        ctx.font = "bold 12px 'JetBrains Mono', monospace";
        const textWidth = ctx.measureText(labelText).width;
        ctx.fillRect(bx, by - 22, textWidth + 10, 22);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(labelText, bx + 5, by - 6);
      }
    }
  }

  // ============================================================================
  // PATIENT TOF (VL53L7CX) 8x8 SPATIAL DEPTH MATRIX & PROXIMITY RADAR
  // ============================================================================
  let patientTofInitialized = false;
  let lastObstacleDist = 2.4;
  let lastObstacleSector = "CENTER";
  let patientHighContrast = false;

  function initPatientTofGrid() {
    const grid = document.getElementById("patientTofGrid");
    if (!grid || patientTofInitialized) return;
    patientTofInitialized = true;

    grid.innerHTML = "";
    // Create 64 cells for the 8x8 matrix
    for (let i = 0; i < 64; i++) {
      const row = Math.floor(i / 8);
      const col = i % 8;
      const cell = document.createElement("div");
      cell.className = "tof-cell cell-clear";
      cell.dataset.idx = String(i);
      cell.dataset.row = String(row);
      cell.dataset.col = String(col);
      cell.setAttribute("role", "gridcell");
      cell.setAttribute("tabindex", "0");
      cell.setAttribute("title", `Zone (${row},${col}): > 2.0m`);
      cell.textContent = "2.4";

      cell.addEventListener("focus", () => {
        announceCellReading(row, col, cell.textContent);
      });

      grid.appendChild(cell);
    }

    // Voice Readout Button
    document.getElementById("btnPatientVoiceReadout")?.addEventListener("click", () => {
      speakPatientGuidance();
    });

    // High Contrast Button
    document.getElementById("btnToggleHighContrast")?.addEventListener("click", () => {
      patientHighContrast = !patientHighContrast;
      const portal = document.getElementById("patientPortal");
      if (portal) portal.classList.toggle("patient-high-contrast", patientHighContrast);
    });
  }

  function announceCellReading(row, col, dist) {
    if (!('speechSynthesis' in window)) return;
    const msg = `Row ${row + 1}, Column ${col + 1}. Distance: ${dist} meters.`;
    const utter = new SpeechSynthesisUtterance(msg);
    utter.rate = 1.1;
    window.speechSynthesis.speak(utter);
  }

  function speakPatientGuidance() {
    if (!('speechSynthesis' in window)) {
      alert(`Audio Navigation: Nearest obstacle is ${lastObstacleDist.toFixed(1)}m in ${lastObstacleSector} direction.`);
      return;
    }
    window.speechSynthesis.cancel();
    let text = "";
    if (lastObstacleDist < 0.6) {
      text = `Danger! Obstacle very close, ${lastObstacleDist.toFixed(1)} meters directly ${lastObstacleSector.toLowerCase()}!`;
    } else if (lastObstacleDist < 1.4) {
      text = `Caution: Obstacle detected ${lastObstacleDist.toFixed(1)} meters in your ${lastObstacleSector.toLowerCase()} sector. Path ahead is narrowing.`;
    } else {
      text = `Path ahead is clear. Nearest detected object is ${lastObstacleDist.toFixed(1)} meters away. Surface and overhead clearance safe.`;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.pitch = 1.05;
    window.speechSynthesis.speak(utter);
  }

  function updatePatientTofTelemetry(event) {
    const grid = document.getElementById("patientTofGrid");
    if (!grid) return;

    if (!patientTofInitialized) {
      initPatientTofGrid();
    }

    const dist = event.distance_m || 2.4;
    lastObstacleDist = dist;
    lastObstacleSector = event.motor_channel || "CENTER";

    // 1. Synthesize or consume 8x8 matrix
    let matrix = event.depth_matrix;
    if (!matrix || !Array.isArray(matrix) || matrix.length < 8) {
      // Build realistic 8x8 matrix from current telemetry event
      matrix = [];
      const targetCol = event.motor_channel === "LEFT" ? 1 : (event.motor_channel === "RIGHT" ? 6 : 3);
      for (let r = 0; r < 8; r++) {
        const row = [];
        for (let c = 0; c < 8; c++) {
          const colDist = Math.abs(c - targetCol);
          const rowDist = Math.abs(r - 4);
          const spread = Math.sqrt(colDist * colDist + rowDist * rowDist);
          let cellM = Math.min(4.0, dist + spread * 0.45 + (Math.sin(r + c) * 0.08));
          if (r < 2 && event.is_head_hazard) cellM = Math.min(cellM, 1.1); // Overhead hazard
          row.push(parseFloat(cellM.toFixed(2)));
        }
        matrix.push(row);
      }
    }

    // 2. Update each of the 64 cells in the DOM
    const cells = grid.children;
    let minLeft = 4.0, minCenter = 4.0, minRight = 4.0;
    let minOverhead = 4.0, minGround = 4.0;

    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const idx = r * 8 + c;
        const cell = cells[idx];
        if (!cell) continue;

        const val = matrix[r] && matrix[r][c] !== undefined ? matrix[r][c] : 3.0;

        // Categorize sector
        if (c <= 2) minLeft = Math.min(minLeft, val);
        else if (c <= 4) minCenter = Math.min(minCenter, val);
        else minRight = Math.min(minRight, val);

        // Categorize elevation
        if (r <= 1) minOverhead = Math.min(minOverhead, val);
        if (r >= 6) minGround = Math.min(minGround, val);

        // Styling based on depth
        cell.className = "tof-cell";
        if (val < 0.5) {
          cell.classList.add("cell-critical");
        } else if (val < 1.2) {
          cell.classList.add("cell-warning");
        } else if (val < 2.0) {
          cell.classList.add("cell-notice");
        } else {
          cell.classList.add("cell-clear");
        }

        cell.textContent = val < 2.0 ? val.toFixed(1) : "";
        cell.setAttribute("title", `Zone [Row ${r+1}, Col ${c+1}]: ${val.toFixed(2)}m`);
      }
    }

    // 3. Update 3-Zone Proximity Gauges
    updateSectorMeter("Left", minLeft);
    updateSectorMeter("Center", minCenter);
    updateSectorMeter("Right", minRight);

    // 4. Update Active Haptic Motor Pill
    const hapticPill = document.getElementById("patientActiveHapticPill");
    if (hapticPill) {
      if (event.should_pulse && event.motor_channel) {
        hapticPill.textContent = `PULSING: ${event.motor_channel} MOTOR (CH${event.motor_channel === "LEFT" ? 5 : (event.motor_channel === "CENTER" ? 1 : 2)})`;
        hapticPill.className = "badge-pill critical active-motor-buzz";
      } else {
        hapticPill.textContent = "MOTORS: QUIET (CLEAR)";
        hapticPill.className = "badge-pill safe";
      }
    }

    // 5. Update Elevation Hazard Bins
    const overheadTag = document.getElementById("elevOverheadTag");
    const overheadText = document.getElementById("elevOverheadText");
    if (minOverhead < 1.4 || event.is_head_hazard) {
      if (overheadTag) { overheadTag.textContent = "Low Clearance"; overheadTag.className = "risk-tag critical"; }
      if (overheadText) overheadText.textContent = `Overhead hazard detected at ${minOverhead.toFixed(2)}m`;
    } else {
      if (overheadTag) { overheadTag.textContent = "Clear"; overheadTag.className = "risk-tag low"; }
      if (overheadText) overheadText.textContent = "No low-hanging branches or doorframes (>2.0m)";
    }

    const groundTag = document.getElementById("elevGroundTag");
    const groundText = document.getElementById("elevGroundText");
    if (minGround < 0.6) {
      if (groundTag) { groundTag.textContent = "Step / Curb"; groundTag.className = "risk-tag moderate"; }
      if (groundText) groundText.textContent = `Elevation change ahead at ${minGround.toFixed(2)}m`;
    } else {
      if (groundTag) { groundTag.textContent = "Safe Path"; groundTag.className = "risk-tag low"; }
      if (groundText) groundText.textContent = "Smooth pavement detected ahead";
    }
  }

  function updateSectorMeter(sectorName, distanceVal) {
    const distEl = document.getElementById(`secDist${sectorName}`);
    const meterEl = document.getElementById(`secMeter${sectorName}`);
    const statusEl = document.getElementById(`secStatus${sectorName}`);
    const cardEl = document.getElementById(`sectorCard${sectorName}`);

    if (distEl) distEl.textContent = `${distanceVal.toFixed(2)} m`;

    // Meter fill: 0m = 100% full, 3.5m = 0%
    const pct = Math.max(5, Math.min(100, ((3.5 - distanceVal) / 3.5) * 100));
    if (meterEl) meterEl.style.width = `${pct.toFixed(0)}%`;

    if (cardEl) {
      cardEl.classList.remove("critical-state", "warning-state", "safe-state");
      if (distanceVal < 0.6) {
        cardEl.classList.add("critical-state");
        if (statusEl) { statusEl.textContent = "Danger!"; statusEl.style.color = "#ef4444"; }
      } else if (distanceVal < 1.4) {
        cardEl.classList.add("warning-state");
        if (statusEl) { statusEl.textContent = "Caution"; statusEl.style.color = "#f59e0b"; }
      } else {
        cardEl.classList.add("safe-state");
        if (statusEl) { statusEl.textContent = "Clear"; statusEl.style.color = "#10b981"; }
      }
    }
  }

  // ============================================================================
  // VL53L7CX 8x8 DEPTH GRID (cm) — LIVE RESEARCHER & PATIENT VISUALIZATION
  // ============================================================================
  function updateDepthGrid() {
    const researcherContainer = document.getElementById('tofDepthGrid');
    const patientGrid = document.getElementById('patientTofGrid');
    if (!researcherContainer && !patientGrid) return;
    const tok = authToken || '';
    fetch(`/api/depth_grid?token=${tok}`)
      .then(r => r.json())
      .then(data => {
        if (!data.grid) return;
        const grid = data.grid; // 8x8 array in cm

        // 1. Render Researcher Grid
        if (researcherContainer) {
          researcherContainer.innerHTML = '';
          for (let row = 0; row < 8; row++) {
            for (let col = 0; col < 8; col++) {
              const val = (grid[row] && grid[row][col] != null) ? grid[row][col] : -1;
              const cell = document.createElement('div');
              cell.className = 'tof-cell';
              if (val <= 5 || val >= 400) {
                cell.classList.add('oor');
                cell.textContent = '---';
              } else if (val < 30) {
                cell.classList.add('danger');
                cell.textContent = Math.round(val) + '!';
              } else if (val < 100) {
                cell.classList.add('caution');
                cell.textContent = Math.round(val);
              } else {
                cell.classList.add('safe');
                cell.textContent = Math.round(val);
              }
              researcherContainer.appendChild(cell);
            }
          }
        }

        // 2. Render Patient Grid
        if (patientGrid) {
          const cells = patientGrid.querySelectorAll('.tof-cell');
          if (cells.length === 64) {
            for (let i = 0; i < 64; i++) {
              const r = Math.floor(i / 8);
              const c = i % 8;
              const v = (grid[r] && grid[r][c] != null) ? grid[r][c] : -1;
              const cell = cells[i];
              cell.className = 'tof-cell';
              if (v <= 5 || v >= 400) {
                cell.classList.add('cell-oor');
                cell.textContent = '---';
              } else if (v < 30) {
                cell.classList.add('cell-critical');
                cell.textContent = Math.round(v) + 'cm';
              } else if (v < 100) {
                cell.classList.add('cell-warning');
                cell.textContent = Math.round(v) + 'cm';
              } else {
                cell.classList.add('cell-clear');
                cell.textContent = Math.round(v) + 'cm';
              }
            }
          }
        }

        // 3. Update 3-Zone Direction Bins & Neckband Motors directly from real ToF grid
        let minLeftCm = 999.0, minCenterCm = 999.0, minRightCm = 999.0;
        let minOverheadCm = 999.0, minGroundCm = 999.0;

        for (let r = 0; r < 8; r++) {
          for (let c = 0; c < 8; c++) {
            const val = (grid[r] && grid[r][c] != null) ? grid[r][c] : -1;
            if (val > 5 && val < 400) {
              if (c <= 2) minLeftCm = Math.min(minLeftCm, val);
              else if (c <= 4) minCenterCm = Math.min(minCenterCm, val);
              else minRightCm = Math.min(minRightCm, val);

              if (r <= 2) minOverheadCm = Math.min(minOverheadCm, val);
              if (r >= 5) minGroundCm = Math.min(minGroundCm, val);
            }
          }
        }

        const dLeftM = minLeftCm < 900 ? (minLeftCm / 100.0) : 4.0;
        const dCenterM = minCenterCm < 900 ? (minCenterCm / 100.0) : 4.0;
        const dRightM = minRightCm < 900 ? (minRightCm / 100.0) : 4.0;
        const dOverheadM = minOverheadCm < 900 ? (minOverheadCm / 100.0) : 4.0;
        const dGroundM = minGroundCm < 900 ? (minGroundCm / 100.0) : 4.0;

        updateSectorMeter("Left", dLeftM);
        updateSectorMeter("Center", dCenterM);
        updateSectorMeter("Right", dRightM);

        const hapticPill = document.getElementById("patientActiveHapticPill");
        if (hapticPill) {
          const buzzing = [];
          const caution = [];
          if (dLeftM < 0.35) buzzing.push("LEFT");
          else if (dLeftM < 1.4) caution.push("LEFT");
          if (dCenterM < 0.35) buzzing.push("CENTER");
          else if (dCenterM < 1.4) caution.push("CENTER");
          if (dRightM < 0.35) buzzing.push("RIGHT");
          else if (dRightM < 1.4) caution.push("RIGHT");

          if (buzzing.length > 0) {
            hapticPill.textContent = `BUZZING: ${buzzing.join(" & ")}`;
            hapticPill.className = "badge-pill critical active-motor-buzz";
          } else if (caution.length > 0) {
            hapticPill.textContent = `MOTORS: ${caution.join(" & ")} — Obstacle Nearby`;
            hapticPill.className = "badge-pill approaching";
          } else {
            hapticPill.textContent = "MOTORS: QUIET";
            hapticPill.className = "badge-pill safe";
          }
        }

        // 4. Update Elevation Hazard Bins
        const overheadTag = document.getElementById("elevOverheadTag");
        const overheadText = document.getElementById("elevOverheadText");
        if (dOverheadM < 1.4) {
          if (overheadTag) { overheadTag.textContent = "Low Clearance"; overheadTag.className = "risk-tag critical"; }
          if (overheadText) overheadText.textContent = `Overhead hazard detected at ${dOverheadM.toFixed(2)}m`;
        } else {
          if (overheadTag) { overheadTag.textContent = "Clear"; overheadTag.className = "risk-tag low"; }
          if (overheadText) overheadText.textContent = "No low-hanging branches or doorframes (>2.0m)";
        }

        const groundTag = document.getElementById("elevGroundTag");
        const groundText = document.getElementById("elevGroundText");
        if (dGroundM < 0.6) {
          if (groundTag) { groundTag.textContent = "Step / Curb"; groundTag.className = "risk-tag moderate"; }
          if (groundText) groundText.textContent = `Elevation change ahead at ${dGroundM.toFixed(2)}m`;
        } else {
          if (groundTag) { groundTag.textContent = "Safe Path"; groundTag.className = "risk-tag low"; }
          if (groundText) groundText.textContent = "Smooth pavement detected ahead";
        }
      })
      .catch(() => {});
  }
  setInterval(updateDepthGrid, 500);

  // Initial setup: draw radar & check auth session
  drawRadar();
  initPatientTofGrid();
  initGuardianCamera();
  checkExistingSession();
});


  // Auto-reconnect stream images if connection dropped or started before backend was ready
  function ensureStreamConnected(imgId) {
    const img = document.getElementById(imgId);
    if (!img) return;
    img.onerror = () => {
      console.warn(`[Stream] Reconnecting ${imgId}...`);
      setTimeout(() => {
        img.src = "/api/video_feed?t=" + Date.now();
      }, 2000);
    };
  }
  ensureStreamConnected("guardianCamPreviewImg");
  ensureStreamConnected("guardianMainStreamImg");
