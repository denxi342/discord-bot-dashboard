/**
 * Voice Recorder Module
 * Handles voice message recording with waveform visualization
 */

const VoiceRecorder = {
    // State
    mediaRecorder: null,
    audioChunks: [],
    audioContext: null,
    analyser: null,
    animationId: null,
    startTime: null,
    timerInterval: null,
    isRecording: false,

    /**
     * Initialize and start recording
     */
    async startRecording() {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // Initialize MediaRecorder
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            this.mediaRecorder = new MediaRecorder(stream, { mimeType });
            this.audioChunks = [];
            this.isRecording = true;

            // Setup Web Audio API for visualization
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);

            // Handle data
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            // Handle stop
            this.mediaRecorder.onstop = () => {
                this.stopVisualization();
                stream.getTracks().forEach(track => track.stop());
            };

            // Start recording
            this.mediaRecorder.start();
            this.startTime = Date.now();

            // Show recording UI
            this.showRecordingUI();

            // Start timer and visualization
            this.startTimer();
            this.startVisualization();

        } catch (error) {
            console.error('Error starting recording:', error);
            if (error.name === 'NotAllowedError') {
                Utils.showToast('❌ Доступ к микрофону запрещен', 'error');
            } else {
                Utils.showToast('❌ Ошибка записи аудио', 'error');
            }
        }
    },

    /**
     * Stop recording and return audio blob
     */
    async stopRecording() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
                resolve(null);
                return;
            }

            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
                const duration = Math.round((Date.now() - this.startTime) / 1000);

                this.cleanup();
                resolve({ blob, duration });
            };

            this.mediaRecorder.stop();
            this.isRecording = false;
            this.stopTimer();
        });
    },

    /**
     * Cancel recording
     */
    cancelRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        this.cleanup();
        this.hideRecordingUI();
    },

    /**
     * Show recording UI modal
     */
    showRecordingUI() {
        const modal = document.createElement('div');
        modal.id = 'voice-recorder-modal';
        modal.className = 'voice-recorder-modal';
        modal.innerHTML = `
            <div class="voice-recorder-content">
                <div class="voice-recorder-header">
                    <h3><i class="fa-solid fa-microphone"></i> Запись голосового сообщения</h3>
                    <button class="close-recorder" onclick="VoiceRecorder.cancelRecording()">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
                
                <div class="waveform-container">
                    <canvas id="waveform-canvas"></canvas>
                </div>
                
                <div class="recording-timer" id="recording-timer">00:00</div>
                
                <div class="recording-controls">
                    <button class="btn-cancel" onclick="VoiceRecorder.cancelRecording()">
                        <i class="fa-solid fa-trash"></i> Отменить
                    </button>
                    <div class="recording-indicator">
                        <div class="pulse-dot"></div>
                        <span>Идет запись...</span>
                    </div>
                    <button class="btn-send" onclick="VoiceRecorder.sendRecording()">
                        <i class="fa-solid fa-paper-plane"></i> Отправить
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Initialize canvas
        this.canvas = document.getElementById('waveform-canvas');
        this.canvasCtx = this.canvas.getContext('2d');
        this.canvas.width = this.canvas.offsetWidth * 2;
        this.canvas.height = this.canvas.offsetHeight * 2;
    },

    /**
     * Hide recording UI
     */
    hideRecordingUI() {
        const modal = document.getElementById('voice-recorder-modal');
        if (modal) {
            modal.remove();
        }
    },

    /**
     * Start recording timer
     */
    startTimer() {
        const timerEl = document.getElementById('recording-timer');
        if (!timerEl) return;

        this.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            timerEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }, 1000);
    },

    /**
     * Stop timer
     */
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    },

    /**
     * Start waveform visualization
     */
    startVisualization() {
        if (!this.analyser || !this.canvas) return;

        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
            this.animationId = requestAnimationFrame(draw);

            this.analyser.getByteTimeDomainData(dataArray);

            this.canvasCtx.fillStyle = '#2b2d31';
            this.canvasCtx.fillRect(0, 0, this.canvas.width, this.canvas.height);

            this.canvasCtx.lineWidth = 4;
            this.canvasCtx.strokeStyle = '#5865f2';
            this.canvasCtx.beginPath();

            const sliceWidth = this.canvas.width / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const v = dataArray[i] / 128.0;
                const y = v * this.canvas.height / 2;

                if (i === 0) {
                    this.canvasCtx.moveTo(x, y);
                } else {
                    this.canvasCtx.lineTo(x, y);
                }

                x += sliceWidth;
            }

            this.canvasCtx.lineTo(this.canvas.width, this.canvas.height / 2);
            this.canvasCtx.stroke();
        };

        draw();
    },

    /**
     * Stop visualization
     */
    stopVisualization() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    },

    /**
     * Send recording to chat
     */
    async sendRecording() {
        const result = await this.stopRecording();
        if (!result) return;

        this.hideRecordingUI();

        // Convert blob to data URI
        const reader = new FileReader();
        reader.onloadend = async () => {
            const dataUri = reader.result;

            // Create attachment object for voice message
            const voiceAttachment = {
                type: 'voice',
                url: dataUri,
                duration: result.duration,
                name: `voice_${Date.now()}.webm`
            };

            // Send via existing message system
            if (typeof DiscordModule !== 'undefined') {
                if (DiscordModule.activeDM) {
                    // Send to DM
                    await DiscordModule.sendDMMessage(DiscordModule.activeDM, '', [voiceAttachment]);
                } else if (DiscordModule.currentChannel) {
                    // Send to channel
                    await DiscordModule.sendMessage(DiscordModule.currentChannel, '', [voiceAttachment]);
                }
            }
        };
        reader.readAsDataURL(result.blob);
    },

    /**
     * Cleanup resources
     */
    cleanup() {
        this.stopVisualization();
        this.stopTimer();

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.analyser = null;
        this.isRecording = false;
    },

    /**
     * Render voice message player in chat
     */
    renderVoiceMessage(messageData) {
        const { audio_url, duration, timestamp, author, isOwn } = messageData;

        const playerId = `voice-player-${Date.now()}-${Math.random()}`;

        return `
            <div class="voice-message-player" data-audio="${audio_url}" data-duration="${duration}" id="${playerId}">
                <button class="voice-play-btn" onclick="VoiceRecorder.togglePlayback('${playerId}')">
                    <i class="fa-solid fa-play"></i>
                </button>
                <div class="voice-waveform-static">
                    ${this.generateStaticWaveform()}
                </div>
                <div class="voice-duration">${this.formatDuration(duration)}</div>
                <select class="voice-speed" onchange="VoiceRecorder.changeSpeed('${playerId}', this.value)">
                    <option value="1">1x</option>
                    <option value="1.5">1.5x</option>
                    <option value="2">2x</option>
                </select>
            </div>
        `;
    },

    /**
     * Generate static waveform visualization
     */
    generateStaticWaveform() {
        const bars = 30;
        let html = '';
        for (let i = 0; i < bars; i++) {
            const height = Math.random() * 60 + 20;
            html += `<div class="waveform-bar" style="height: ${height}%"></div>`;
        }
        return html;
    },

    /**
     * Toggle playback
     */
    togglePlayback(playerId) {
        const player = document.getElementById(playerId);
        if (!player) return;

        const btn = player.querySelector('.voice-play-btn i');
        const audioUrl = player.dataset.audio;

        // Get or create audio element
        let audio = player.audioElement;
        if (!audio) {
            audio = new Audio(audioUrl);
            player.audioElement = audio;

            audio.onended = () => {
                btn.className = 'fa-solid fa-play';
            };
        }

        if (audio.paused) {
            audio.play();
            btn.className = 'fa-solid fa-pause';
        } else {
            audio.pause();
            btn.className = 'fa-solid fa-play';
        }
    },

    /**
     * Change playback speed
     */
    changeSpeed(playerId, speed) {
        const player = document.getElementById(playerId);
        if (!player || !player.audioElement) return;

        player.audioElement.playbackRate = parseFloat(speed);
    },

    /**
     * Format duration (seconds to MM:SS)
     */
    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${String(secs).padStart(2, '0')}`;
    }
};

// Export to global scope
window.VoiceRecorder = VoiceRecorder;
