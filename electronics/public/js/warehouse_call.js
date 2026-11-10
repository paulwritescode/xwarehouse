(function () {
	const mount = document.getElementById("xw-call-app");
	if (!mount) return;
	if (!window.Vue) { mount.innerHTML = '<div class="xw-call-auth"><h1>Call centre unavailable</h1><p>The Vue client did not load. Refresh the page while connected to the network.</p></div>'; return; }
	const { createApp } = window.Vue;
	function frappe_call(method, args) { return new Promise((resolve, reject) => frappe.call({ method, args: args || {}, callback: (response) => response && response.exc ? reject(response.exc) : resolve(response ? response.message : null), error: reject })); }
	createApp({
		data() { return { session: null, loading: true, answering: false, voiceState: "idle", voiceError: "", microphoneBlocked: false, voiceMuted: false, voicePeerConnection: null, voiceDataChannel: null, voiceMediaStream: null, voiceKeepAlive: null, error: "", authRequired: false, inCall: false }; },
		computed: {
			parsedSummary() { if (!this.session || !this.session.summary_json) return {}; try { return JSON.parse(this.session.summary_json); } catch (e) { return {}; } },
			isReady() { return this.session && ["Scheduled", "Ready"].includes(this.session.status); },
			voiceActive() { return ["connecting", "connected", "error"].includes(this.voiceState); },
			voiceStatusLabel() { return { connecting: "Connecting", connected: "Live", error: "Connection issue" }[this.voiceState] || "Ready"; },
			voiceHelpText() { return this.voiceState === "connecting" ? "Requesting your microphone and connecting securely to the warehouse voice agent…" : this.voiceState === "connected" ? "You are connected. Speak naturally; the agent can answer warehouse questions and use the approved warehouse tools." : "The voice connection could not be started. Check that the Pipecat service is running, then try again."; },
			microphoneFallbackUrl() { const port = window.location.port ? `:${window.location.port}` : ""; return `http://localhost${port}${window.location.pathname}${window.location.search}`; },
			formattedDate() { return this.session && this.session.scheduled_for ? new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" }).format(new Date(this.session.scheduled_for)) : "Today"; },
			currency() { return (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(Number(value || 0)); },
			number() { return (value) => new Intl.NumberFormat().format(Number(value || 0)); },
		},
		methods: {
			async load() { this.loading = true; this.error = ""; this.authRequired = false; try { this.session = await frappe_call("electronics.x_electronics_warehouse.api.get_latest_admin_call_session"); } catch (error) { this.authRequired = true; } finally { this.loading = false; } },
			async simulateCall() { this.loading = true; this.error = ""; this.authRequired = false; try { this.session = await frappe_call("electronics.x_electronics_warehouse.api.create_daily_admin_call_session"); } catch (error) { this.error = "Could not create today's summary. Check your warehouse permissions."; } finally { this.loading = false; } },
			voiceBaseUrl() { return (window.XW_VOICE_AGENT_URL || "http://localhost:7860").replace(/\/+$/, ""); },
			voiceBody() { return { source: "xwarehouse-call-centre", session_name: this.session && this.session.name, summary_title: this.session && this.session.summary_title, warehouse_context: this.session && this.session.summary_text }; },
			async waitForIceGathering(peerConnection) { if (peerConnection.iceGatheringState === "complete") return; await new Promise((resolve) => { let finished = false; const finish = () => { if (finished) return; finished = true; clearTimeout(timeout); peerConnection.removeEventListener("icegatheringstatechange", onStateChange); resolve(); }; const onStateChange = () => { if (peerConnection.iceGatheringState === "complete") finish(); }; const timeout = setTimeout(finish, 8000); peerConnection.addEventListener("icegatheringstatechange", onStateChange); }); },
			setupVoiceDataChannel(channel) {
				this.voiceDataChannel = channel;
				channel.onopen = () => {
					channel.send(JSON.stringify({ type: "signalling", message: { type: "trackStatus", receiver_index: 0, enabled: true } }));
					channel.send(JSON.stringify({ type: "signalling", message: { type: "trackStatus", receiver_index: 1, enabled: false } }));
					channel.send(JSON.stringify({ label: "rtvi-ai", type: "client-ready", data: { version: "2.1.0", about: { library: "xwarehouse-call-centre", library_version: "1.0.0" } }, id: "xwarehouse" }));
					this.voiceKeepAlive = window.setInterval(() => { if (channel.readyState === "open") channel.send(`ping: ${Date.now()}`); }, 1000);
				};
				channel.onmessage = (event) => {
					if (typeof event.data !== "string") return;
					try { const message = JSON.parse(event.data); if (message.label === "rtvi-ai" && message.type === "error") this.voiceError = message.data && (message.data.message || message.data.error) || "The voice agent returned an error."; } catch (error) { /* keep-alive messages are plain text */ }
				};
			},
			async startVoiceCall() {
				if (this.voiceState === "connecting" || this.voiceState === "connected") return;
				this.voiceState = "connecting"; this.voiceError = ""; this.microphoneBlocked = false; this.error = "";
				let peerConnection;
				try {
					if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { this.microphoneBlocked = true; throw new Error("Microphone access is blocked on this address. Use localhost or HTTPS for the call-centre page."); }
					const startResponse = await fetch(`${this.voiceBaseUrl()}/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transport: "webrtc", enableDefaultIceServers: true, body: this.voiceBody() }) });
					if (!startResponse.ok) throw new Error(`Pipecat /start returned HTTP ${startResponse.status}.`);
					const start = await startResponse.json();
					if (!start.sessionId) throw new Error("Pipecat did not return a WebRTC session.");
					peerConnection = new RTCPeerConnection(start.iceConfig || {});
					this.voicePeerConnection = peerConnection;
					peerConnection.addTransceiver("audio", { direction: "sendrecv" });
					peerConnection.addTransceiver("video", { direction: "sendrecv" });
					this.setupVoiceDataChannel(peerConnection.createDataChannel("chat", { ordered: true }));
					peerConnection.ontrack = (event) => { if (event.track.kind !== "audio") return; const audio = this.$refs.remoteAudio; if (!audio) return; audio.srcObject = new MediaStream([event.track]); audio.play().catch(() => {}); };
					peerConnection.onconnectionstatechange = () => { if (peerConnection.connectionState === "connected") this.voiceState = "connected"; if (["failed", "closed"].includes(peerConnection.connectionState) && this.voiceState !== "idle") { this.voiceState = "error"; this.voiceError = "The WebRTC connection ended unexpectedly."; } };
					this.voiceMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
					const audioTransceiver = peerConnection.getTransceivers().find((transceiver) => transceiver.receiver && transceiver.receiver.track && transceiver.receiver.track.kind === "audio");
					if (!audioTransceiver) throw new Error("The browser could not prepare an audio channel.");
					await audioTransceiver.sender.replaceTrack(this.voiceMediaStream.getAudioTracks()[0]);
					const offer = await peerConnection.createOffer();
					await peerConnection.setLocalDescription(offer);
					await this.waitForIceGathering(peerConnection);
					const offerResponse = await fetch(`${this.voiceBaseUrl()}/sessions/${encodeURIComponent(start.sessionId)}/api/offer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sdp: peerConnection.localDescription.sdp, type: peerConnection.localDescription.type, request_data: this.voiceBody() }) });
					if (!offerResponse.ok) throw new Error(`Pipecat /api/offer returned HTTP ${offerResponse.status}.`);
					const answer = await offerResponse.json();
					await peerConnection.setRemoteDescription(answer);
					if (this.session && this.isReady) this.session = await frappe_call("electronics.x_electronics_warehouse.api.update_admin_call_session", { name: this.session.name, status: "In Progress" });
				} catch (error) {
					this.voiceError = error && error.message ? error.message : "The voice call could not be started.";
					this.voiceState = "error";
					this.cleanupVoiceConnection();
				}
			},
			toggleMute() { if (!this.voiceMediaStream) return; this.voiceMuted = !this.voiceMuted; this.voiceMediaStream.getAudioTracks().forEach((track) => { track.enabled = !this.voiceMuted; }); if (this.voiceDataChannel && this.voiceDataChannel.readyState === "open") this.voiceDataChannel.send(JSON.stringify({ type: "signalling", message: { type: "trackStatus", receiver_index: 0, enabled: !this.voiceMuted } })); },
			cleanupVoiceConnection() { if (this.voiceKeepAlive) { window.clearInterval(this.voiceKeepAlive); this.voiceKeepAlive = null; } if (this.voiceDataChannel) { try { this.voiceDataChannel.close(); } catch (error) {} this.voiceDataChannel = null; } if (this.voiceMediaStream) { this.voiceMediaStream.getTracks().forEach((track) => track.stop()); this.voiceMediaStream = null; } if (this.voicePeerConnection) { try { this.voicePeerConnection.close(); } catch (error) {} this.voicePeerConnection = null; } const audio = this.$refs.remoteAudio; if (audio) { audio.pause(); audio.srcObject = null; } this.voiceMuted = false; },
			async endVoiceCall() { this.cleanupVoiceConnection(); this.voiceState = "idle"; if (this.session && this.session.status === "In Progress") { try { this.session = await frappe_call("electronics.x_electronics_warehouse.api.update_admin_call_session", { name: this.session.name, status: "Completed" }); } catch (error) { this.error = "The call ended, but its Frappe status could not be updated."; } } },
			async answer() { if (!this.session) return; this.answering = true; try { this.session = await frappe_call("electronics.x_electronics_warehouse.api.update_admin_call_session", { name: this.session.name, status: "In Progress" }); this.inCall = true; } catch (error) { this.error = "The call could not be answered."; } finally { this.answering = false; } },
			async finish(status) { if (!this.session) return; try { this.session = await frappe_call("electronics.x_electronics_warehouse.api.update_admin_call_session", { name: this.session.name, status }); this.inCall = false; } catch (error) { this.error = "The call could not be updated."; } },
		},
		mounted() { this.load(); if ("serviceWorker" in navigator) navigator.serviceWorker.register("/assets/electronics/warehouse-pwa/sw.js").catch(() => {}); },
		beforeUnmount() { this.cleanupVoiceConnection(); },
		template: `
			<div v-if="loading" class="xw-call-loading">Loading call centre…</div>
			<div v-else class="xw-call-shell"><header class="xw-call-top"><div class="xw-call-brand"><span class="xw-call-brand-mark">X</span><span>XWarehouse<small>Administrator call centre</small></span></div><span class="xw-call-user">{{ session ? session.recipient : "Administrator" }}</span></header>
				<div v-if="authRequired" class="xw-call-auth"><h1>Sign in to the call centre</h1><p>The administrator summary contains private warehouse information, so it is available only inside the company workspace.</p><a class="xw-call-button xw-call-button-primary" href="/login?redirect-to=/app/warehouse-call">Sign in</a></div>
				<div v-else-if="error" class="xw-call-auth"><p>{{ error }}</p><button class="xw-call-button xw-call-button-secondary" @click="load">Try again</button></div>
				<div v-else-if="!session" class="xw-call-auth"><h1>No call summary yet</h1><p>The daily session is created at 17:00 by the Frappe scheduler. Use the simulator below to create today's session while testing.</p><button class="xw-call-button xw-call-button-primary" @click="simulateCall">Simulate today's call</button></div>
				<div v-else-if="voiceActive" class="xw-call-card xw-live-call"><div class="xw-live-header"><div><p class="xw-call-kicker">LIVE WAREHOUSE VOICE</p><h1>{{ session.summary_title }}</h1></div><span class="xw-live-status" :class="'is-' + voiceState"><i></i>{{ voiceStatusLabel }}</span></div><div class="xw-live-stage"><div class="xw-live-orb" :class="'is-' + voiceState"><span>AI</span></div><div><strong>{{ voiceState === 'connected' ? 'The agent is listening' : voiceStatusLabel }}</strong><p>{{ voiceHelpText }}</p></div></div><div v-if="voiceError" class="xw-voice-error"><p>{{ voiceError }}</p><a v-if="microphoneBlocked" class="xw-voice-help-link" :href="microphoneFallbackUrl">Open XWarehouse on localhost →</a></div><div class="xw-call-action"><button v-if="voiceState === 'error'" class="xw-call-button xw-call-button-primary" @click="startVoiceCall">Try again</button><button v-if="voiceState === 'connected'" class="xw-call-button xw-call-button-secondary" @click="toggleMute">{{ voiceMuted ? 'Unmute microphone' : 'Mute microphone' }}</button><button class="xw-call-button xw-call-button-ghost xw-live-end" @click="endVoiceCall">End call</button></div><audio ref="remoteAudio" autoplay playsinline></audio></div>
				<div v-else-if="inCall" class="xw-call-card xw-summary-view"><p class="xw-call-kicker">LIVE SUMMARY / {{ formattedDate }}</p><h1>{{ session.summary_title }}</h1><p>{{ session.summary_text }}</p><div class="xw-summary-grid"><div class="xw-summary-stat"><span>Warehouses</span><strong>{{ number(parsedSummary.dashboard && parsedSummary.dashboard.warehouse_count) }}</strong></div><div class="xw-summary-stat"><span>Units on hand</span><strong>{{ number(parsedSummary.dashboard && parsedSummary.dashboard.quantity) }}</strong></div><div class="xw-summary-stat"><span>Sales today</span><strong>{{ number(parsedSummary.sales && parsedSummary.sales.sales_count) }}</strong></div><div class="xw-summary-stat"><span>Review items</span><strong>{{ number((parsedSummary.low_stock || []).length + (parsedSummary.discrepancies || []).length) }}</strong></div></div><div class="xw-summary-foot"><button class="xw-call-button xw-call-button-primary" @click="finish('Completed')">Finish summary</button><span class="xw-call-user">Facts are sourced from submitted warehouse records.</span></div></div>
				<div v-else class="xw-call-layout"><section class="xw-call-card xw-call-hero"><span class="xw-call-kicker">INCOMING ADMINISTRATOR SUMMARY</span><h1>{{ session.summary_title }}</h1><p>Your end-of-day warehouse review is ready. Start a live browser call with the Pipecat voice agent, or preview the summary inside this workspace.</p><div class="xw-call-meta"><div>Scheduled<strong>17:00</strong></div><div>Status<strong>{{ session.status }}</strong></div></div><div class="xw-call-action"><button class="xw-call-button xw-call-button-primary" :disabled="voiceState === 'connecting'" @click="startVoiceCall">{{ voiceState === 'connecting' ? 'Connecting…' : 'Talk to voice agent' }}</button><button class="xw-call-button xw-call-button-ghost" style="margin-left:8px" @click="answer">Preview summary</button><button class="xw-call-button xw-call-button-ghost" style="margin-left:8px" @click="finish('Declined')">Decline</button><small class="xw-voice-note">Call stays on this page · microphone permission required</small></div></section><aside class="xw-call-card xw-call-side"><p class="xw-call-kicker">CALL HISTORY</p><h2>Administrator summaries</h2><p>Each session is kept in Frappe so the next voice channel can open with the right warehouse context.</p><div class="xw-history"><div class="xw-history-item"><strong>{{ session.summary_title }}</strong><small>{{ formattedDate }} · {{ session.status }}</small></div></div><button class="xw-call-link" @click="simulateCall">Refresh / simulate today's session →</button></aside></div>
			</div>
		`,
	}).mount(mount);
})();
