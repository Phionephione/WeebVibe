document.addEventListener('DOMContentLoaded', () => {

    const jikanApiUrl = 'https://api.jikan.moe/v4';

    // --- NEW DYNAMIC HERO SLIDER LOGIC ---
    async function populateHeroSlider() {
        const heroSlider = document.getElementById('hero-slider');
        if (!heroSlider) return;

        try {
            // Fetch the top 5 most popular anime
            const response = await fetch(`${jikanApiUrl}/top/anime?limit=5`);
            if (!response.ok) throw new Error('Failed to fetch top anime for hero banner');
            
            const data = await response.json();
            const topAnime = data.data;

            heroSlider.innerHTML = ''; // Clear any placeholders

            // Create a slide for each of the top 5 anime
            topAnime.forEach((anime, index) => {
                const slide = document.createElement('div');
                slide.className = 'slide';
                // The first slide is made active so it's visible on load
                if (index === 0) {
                    slide.classList.add('active');
                }
                slide.style.backgroundImage = `url('${anime.images.jpg.large_image_url}')`;

                // Truncate the synopsis to a reasonable length
                const synopsis = anime.synopsis ? anime.synopsis.substring(0, 200) + '...' : 'No synopsis available.';

                slide.innerHTML = `
                    <div class="slide-content">
                        <h1 class="anime-title">${anime.title}</h1>
                        <p class="anime-description">${synopsis}</p>
                        <a href="/anime/${anime.mal_id}" class="watch-now-btn">
                            <i class="fas fa-book-open"></i> Read More & Discuss
                        </a>
                    </div>
                `;
                heroSlider.appendChild(slide);
            });

            // --- Logic to automatically rotate the slides ---
            let currentSlideIndex = 0;
            const slides = document.querySelectorAll('.hero-slider .slide');
            const slideCount = slides.length;

            if (slideCount > 1) {
                setInterval(() => {
                    slides[currentSlideIndex].classList.remove('active');
                    currentSlideIndex = (currentSlideIndex + 1) % slideCount;
                    slides[currentSlideIndex].classList.add('active');
                }, 7000); // Rotate every 7 seconds
            }

        } catch (error) {
            console.error('Error fetching hero banner data:', error);
            heroSlider.innerHTML = `<p style="color: white; text-align: center;">Could not load featured anime.</p>`;
        }
    }

    // --- Call the new function to start everything ---
    populateHeroSlider();

    // --- EXISTING CAROUSEL LOGIC (REMAINS THE SAME) ---
    async function populateCarousel(endpoint, carouselId) {
        try {
            const response = await fetch(`${jikanApiUrl}/${endpoint}`);
            if (!response.ok) throw new Error(`Jikan API responded with status: ${response.status}`);
            const data = await response.json();
            const animeList = data.data;
            const carousel = document.getElementById(carouselId);
            if (!carousel) return;
            carousel.innerHTML = '';
            animeList.forEach(anime => {
                const animeCard = document.createElement('div');
                animeCard.className = 'anime-card';
                animeCard.innerHTML = `
                    <a href="/anime/${anime.mal_id}" class="card-link">
                        <div class="card-image">
                            <img src="${anime.images.jpg.large_image_url}" alt="${anime.title}">
                            <div class="play-overlay"><i class="fas fa-book-open"></i></div>
                            <div class="card-meta"><span><i class="fas fa-star"></i> ${anime.score || 'N/A'}</span></div>
                        </div>
                        <h3>${anime.title}</h3>
                    </a>
                `;
                carousel.appendChild(animeCard);
            });
        } catch (error) {
            console.error(`Error fetching data for ${carouselId}:`, error);
            const carousel = document.getElementById(carouselId);
            if (carousel) {
                carousel.innerHTML = `<p style="color: var(--light-text);">Could not load anime. The API might be down.</p>`;
            }
        }
    }

    if (document.getElementById('top-anime-carousel')) {
        populateCarousel('top/anime', 'top-anime-carousel');
    }
    if (document.getElementById('seasonal-anime-carousel')) {
        populateCarousel('seasons/now', 'seasonal-anime-carousel');
    }

    const carousels = document.querySelectorAll('.anime-carousel-section');
    carousels.forEach(carouselSection => {
        const carousel = carouselSection.querySelector('.anime-carousel');
        const prevBtn = carouselSection.querySelector('.prev-btn');
        const nextBtn = carouselSection.querySelector('.next-btn');
        if (!carousel || !prevBtn || !nextBtn) return;
        const scrollAmount = carousel.offsetWidth * 0.8;
        nextBtn.addEventListener('click', () => carousel.scrollBy({ left: scrollAmount, behavior: 'smooth' }));
        prevBtn.addEventListener('click', () => carousel.scrollBy({ left: -scrollAmount, behavior: 'smooth' }));
    });
});