class AudioPlayer {
    constructor() {
        this.playlist = [];
        this.currentTrackIndex = 0;
        this.player = null; // YT Player instance
        this.isPlaying = false;
        this.volume = 50;
        this.ready = false;

        this.elements = {
            container: document.getElementById('music-widget'),
            playBtn: document.getElementById('music-play'),
            prevBtn: document.getElementById('music-prev'),
            nextBtn: document.getElementById('music-next'),
            title: document.getElementById('music-title'),
            artist: document.getElementById('music-artist'),
            cover: document.getElementById('music-cover'),
            volumeSlider: document.getElementById('music-volume')
        };

        this.init();
    }

    async init() {
        // Load Playlist first
        try {
            const response = await fetch('/static/data/playlist.json');
            this.playlist = await response.json();

            if (this.playlist.length > 0) {
                // Load YouTube API
                this.loadYouTubeAPI();
            }
        } catch (error) {
            console.error('Failed to load playlist:', error);
        }
    }

    loadYouTubeAPI() {
        if (window.YT && window.YT.Player) {
            this.onYouTubeIframeAPIReady();
            return;
        }

        const tag = document.createElement('script');
        tag.src = "https://www.youtube.com/iframe_api";
        const firstScriptTag = document.getElementsByTagName('script')[0];
        firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

        // Global callback for YouTube API
        window.onYouTubeIframeAPIReady = () => this.createPlayer();
    }

    createPlayer() {
        // Create a hidden div for the player if it doesn't exist
        let playerDiv = document.getElementById('yt-player-hidden');
        if (!playerDiv) {
            playerDiv = document.createElement('div');
            playerDiv.id = 'yt-player-hidden';
            playerDiv.style.position = 'absolute';
            playerDiv.style.top = '-9999px';
            document.body.appendChild(playerDiv);
        }

        this.player = new YT.Player('yt-player-hidden', {
            height: '0',
            width: '0',
            playerVars: {
                'playsinline': 1,
                'controls': 0,
                'disablekb': 1
            },
            events: {
                'onReady': (event) => this.onPlayerReady(event),
                'onStateChange': (event) => this.onPlayerStateChange(event),
                'onError': (event) => this.onPlayerError(event)
            }
        });
    }

    onPlayerReady(event) {
        this.ready = true;
        this.setupEventListeners();
        this.elements.container.style.display = 'flex'; // Show widget
        this.loadTrack(0, false); // Load first track, don't auto-play immediately unless needed
    }

    togglePlay() {
        if (!this.ready) return;

        // Optimistic UI update
        this.isPlaying = !this.isPlaying;
        this.updatePlayButton();

        if (this.isPlaying) {
            this.player.playVideo();
        } else {
            this.player.pauseVideo();
        }
    }

    updatePlayButton() {
        if (this.isPlaying) {
            this.elements.playBtn.innerHTML = '<i class="fas fa-pause"></i>';
        } else {
            this.elements.playBtn.innerHTML = '<i class="fas fa-play"></i>';
        }
    }

    onPlayerStateChange(event) {
        // YT.PlayerState.ENDED = 0
        if (event.data === 0) {
            this.next();
        }
        // YT.PlayerState.PLAYING = 1
        if (event.data === 1) {
            this.isPlaying = true;
            this.updatePlayButton();
        }
        // YT.PlayerState.PAUSED = 2
        if (event.data === 2) {
            this.isPlaying = false;
            this.updatePlayButton();
        }
    }

    onPlayerError(event) {
        console.error("YouTube Player Error:", event.data);
        // Try next track if error (e.g., restricted video)
        // this.next(); 
    }

    loadTrack(index, autoPlay = true) {
        if (!this.ready) return;
        if (index < 0) index = this.playlist.length - 1;
        if (index >= this.playlist.length) index = 0;

        this.currentTrackIndex = index;
        const track = this.playlist[index];

        this.elements.title.textContent = track.title;
        this.elements.artist.textContent = track.artist;
        this.elements.cover.src = track.cover || 'https://via.placeholder.com/50';

        if (track.type === 'youtube') {
            this.player.loadVideoById(track.url);
            if (!autoPlay) {
                this.player.pauseVideo(); // loadVideoById auto-plays by default
            }
        } else {
            console.warn("Only YouTube supported currently");
        }

        this.player.setVolume(this.volume);
    }

    next() {
        this.loadTrack(this.currentTrackIndex + 1);
    }

    prev() {
        this.loadTrack(this.currentTrackIndex - 1);
    }

    setVolume(value) {
        this.volume = value;
        if (this.player && this.ready) {
            this.player.setVolume(this.volume);
        }
    }

    setupEventListeners() {
        // Remove old listeners to avoid duplicates if re-init (basic implementation)
        // ideally use named functions, but for SPA restart this is okay-ish if we don't re-instantiate class

        this.elements.playBtn.onclick = () => this.togglePlay();
        this.elements.nextBtn.onclick = () => this.next();
        this.elements.prevBtn.onclick = () => this.prev();

        if (this.elements.volumeSlider) {
            this.elements.volumeSlider.oninput = (e) => this.setVolume(e.target.value);
        }
    }
}

// Initialize globally
window.ArizonaMusic = new AudioPlayer();
