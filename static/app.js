const IMG_BASE = "https://image.tmdb.org/t/p/";
const POSTER = IMG_BASE + "w342";
const BACKDROP = IMG_BASE + "w1280";
const STILL = IMG_BASE + "w300";

function esc(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

let currentSection = "home";
let animeCurrentGenre = null;
let animeSort = "popular"; // "popular" or "top_rated"
let animeAdult = false;

// --- API helpers ---
async function api(path) {
  const resp = await fetch(path);
  return resp.json();
}

async function apiPost(path, body) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: false, error: `Server error (${resp.status})` };
  }
}

// --- Init ---
function setupMobileSearch() {
  if (window.innerWidth > 768) return;
  const headerLeft = document.querySelector(".header-left");
  if (headerLeft.querySelector(".search-box-mobile")) return;
  const box = document.createElement("div");
  box.className = "search-box-mobile";
  box.innerHTML = `<input type="text" placeholder="Buscar..." onkeydown="if(event.key==='Enter')doSearch(this.value)">
    <button onclick="doSearch(this.previousElementSibling.value)" aria-label="Buscar">&#128269;</button>`;
  headerLeft.appendChild(box);
}

async function init() {
  setupMobileSearch();
  const cfg = await api("/api/config");
  if (!cfg.has_api_key) {
    showSetup();
    return;
  }
  navigate("home");
}

function showSetup() {
  document.getElementById("setup-modal").classList.remove("hidden");
}

async function saveApiKey() {
  const key = document.getElementById("api-key-input").value.trim();
  if (!key) return;
  await apiPost("/api/config", { tmdb_api_key: key });
  document.getElementById("setup-modal").classList.add("hidden");
  navigate("home");
}

// --- Navigation ---
function navigate(section) {
  currentSection = section;
  const activeNav = section === "adult" ? "anime" : section;
  document.querySelectorAll(".nav-link").forEach((el) => {
    el.classList.toggle("active", el.dataset.section === activeNav);
  });
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Carregando...</div>';

  if (section === "home") loadHome();
  else if (section === "anime") loadAnime();
  else if (section === "series") loadSeries(null, "popular");
  else if (section === "movies") loadMovies(null, "popular");
  else if (section === "adult") loadAdult();
}

// --- Render helpers ---
function makeCard(item) {
  const title = item.title || item.name || "Sem titulo";
  const poster = item.poster_path ? POSTER + item.poster_path : "";
  const year = (item.release_date || item.first_air_date || "").slice(0, 4);
  const rating = item.vote_average ? item.vote_average.toFixed(1) : "";
  const type = item.media_type || (item.first_air_date ? "tv" : "movie");

  const div = document.createElement("div");
  div.className = "card";
  div.onclick = () => showDetail(item.id, type);
  div.innerHTML = `
    ${poster ? `<img src="${esc(poster)}" alt="${esc(title)}" loading="lazy">` : `<div style="width:100%;height:278px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;font-size:13px;border-radius:4px;">${esc(title)}</div>`}
    <div class="card-info">
      <div class="card-title">${esc(title)}</div>
      <div class="card-meta">
        ${rating ? `<span class="card-rating">${esc(rating)}</span> ` : ""}
        ${esc(year)}
      </div>
    </div>
  `;
  return div;
}

function makeHistoryCard(item) {
  const div = document.createElement("div");
  div.className = "card";
  div.onclick = () => {
    // Search TMDB for this title and show detail
    searchAndShowDetail(item.title);
  };
  div.innerHTML = `
    <div style="width:100%;height:278px;background:linear-gradient(135deg,#1a1a2e,#16213e);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:16px;border-radius:4px;">
      <div style="font-size:28px;margin-bottom:12px;">&#127909;</div>
      <div style="font-size:14px;font-weight:600;text-align:center;margin-bottom:8px;">${esc(item.title)}</div>
      <div style="font-size:12px;color:#808080;">S${esc(String(item.season))}E${esc(String(item.episode))}</div>
    </div>
    <div class="card-info" style="opacity:1;">
      <div class="card-title">${esc(item.title)}</div>
      <div class="card-meta">S${esc(String(item.season))} E${esc(String(item.episode))}</div>
    </div>
  `;
  return div;
}

// Global set to track shown item IDs across all rows (reset per page load)
let _shownIds = new Set();

function makeRow(title, items, type) {
  const section = document.createElement("div");
  section.className = "row";
  section.innerHTML = `<h3 class="row-title">${esc(title)}</h3>`;
  const scroll = document.createElement("div");
  scroll.className = "row-scroll";
  items.forEach((item) => {
    if (item.media_type === "person") return;
    if (!item.media_type) item.media_type = type || "tv";
    const uid = (item.media_type || type || "") + "_" + item.id;
    if (_shownIds.has(uid)) return;
    _shownIds.add(uid);
    scroll.appendChild(makeCard(item));
  });
  section.appendChild(scroll);
  return section;
}

function makeHero(item) {
  const title = item.title || item.name;
  const backdrop = item.backdrop_path ? BACKDROP + item.backdrop_path : "";
  const type = item.media_type || "tv";

  const div = document.createElement("div");
  div.className = "hero";
  div.innerHTML = `
    <div class="hero-bg" style="background-image:url('${esc(backdrop)}')"></div>
    <div class="hero-info">
      <h2>${esc(title)}</h2>
      <p>${esc(item.overview || "")}</p>
      <div class="hero-buttons">
        <button class="btn btn-play" id="hero-play">&#9654; Assistir</button>
        <button class="btn btn-info" id="hero-info">&#9432; Mais Info</button>
      </div>
    </div>
  `;
  div.querySelector("#hero-play").onclick = () => playTitle(title);
  div.querySelector("#hero-info").onclick = () => showDetail(item.id, type);
  return div;
}

// --- Anime (Jikan/MAL) helpers ---
function makeAnimeCard(anime) {
  const title = anime.title || anime.entry?.title || "Sem titulo";
  const poster = anime.images?.jpg?.large_image_url || anime.images?.jpg?.image_url || anime.entry?.images?.jpg?.large_image_url || "";
  const year = anime.year || (anime.aired?.from || "").slice(0, 4) || "";
  const score = anime.score || anime.entry?.score || "";
  const malId = anime.mal_id || anime.entry?.mal_id || 0;

  const div = document.createElement("div");
  div.className = "card";
  div.onclick = () => showAnimeDetail(malId);
  div.innerHTML = `
    ${poster ? `<img src="${esc(poster)}" alt="${esc(title)}" loading="lazy">` : `<div style="width:100%;height:278px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;font-size:13px;border-radius:4px;">${esc(title)}</div>`}
    <div class="card-info">
      <div class="card-title">${esc(title)}</div>
      <div class="card-meta">
        ${score ? `<span class="card-rating">${esc(String(score))}</span> ` : ""}
        ${esc(String(year))}
      </div>
    </div>
  `;
  return div;
}

function makeAnimeRow(title, items, onTitleClick) {
  const section = document.createElement("div");
  section.className = "row";
  const h3 = document.createElement("h3");
  h3.className = "row-title";
  h3.textContent = title;
  if (onTitleClick) {
    h3.style.cursor = "pointer";
    h3.onclick = onTitleClick;
    h3.title = "Ver mais";
  }
  section.appendChild(h3);
  const scroll = document.createElement("div");
  scroll.className = "row-scroll";
  items.forEach((item) => {
    const malId = item.mal_id || item.entry?.mal_id || 0;
    const uid = "anime_" + malId;
    if (_shownIds.has(uid)) return;
    _shownIds.add(uid);
    scroll.appendChild(makeAnimeCard(item));
  });
  section.appendChild(scroll);
  return section;
}

function makeAnimeHero(anime) {
  const title = anime.title || "";
  const image = anime.images?.jpg?.large_image_url || "";
  const synopsis = anime.synopsis || "";
  const malId = anime.mal_id || 0;
  const genres = (anime.genres || []).map((g) => g.name).join(", ");

  const div = document.createElement("div");
  div.className = "hero";
  div.innerHTML = `
    <div class="hero-bg" style="background-image:url('${esc(image)}')"></div>
    <div class="hero-info">
      <h2>${esc(title)}</h2>
      ${genres ? `<p style="color:#aaa;font-size:13px;margin-bottom:4px;">${esc(genres)}</p>` : ""}
      <p>${esc(synopsis)}</p>
      <div class="hero-buttons">
        <button class="btn btn-play">&#9654; Assistir</button>
        <button class="btn btn-info">&#9432; Mais Info</button>
      </div>
    </div>
  `;
  div.querySelector(".btn-play").onclick = () => playTitle(title, null, null, true);
  div.querySelector(".btn-info").onclick = () => showAnimeDetail(malId);
  return div;
}

async function showAnimeDetail(malId) {
  const modal = document.getElementById("detail-modal");
  const backdrop = document.getElementById("detail-backdrop");
  const body = document.getElementById("detail-body");

  modal.classList.remove("hidden");
  body.innerHTML = '<div class="loading">Carregando...</div>';
  backdrop.style.backgroundImage = "";

  const resp = await api(`/api/anime/details?id=${malId}`);
  const data = resp.data;
  if (!data) {
    body.innerHTML = `<p>${esc(resp.error || "Erro ao carregar")}</p>`;
    return;
  }

  const title = data.title || "";
  const titleJp = data.title_japanese || "";
  const image = data.images?.jpg?.large_image_url || "";
  const score = data.score || "";
  const year = data.year || (data.aired?.from || "").slice(0, 4) || "";
  const episodes = data.episodes || "?";
  const status = data.status || "";
  const genres = (data.genres || []).map((g) => g.name).join(", ");
  const demographics = (data.demographics || []).map((d) => d.name).join(", ");
  const studios = (data.studios || []).map((s) => s.name).join(", ");
  const synopsis = data.synopsis || "";
  const rating = data.rating || "";

  if (image) {
    backdrop.style.backgroundImage = `url('${image}')`;
  }

  body.innerHTML = `
    <h2>${esc(title)}</h2>
    ${titleJp ? `<p style="color:#888;font-size:14px;margin-bottom:8px;">${esc(titleJp)}</p>` : ""}
    <div class="meta">
      ${score ? `<span class="rating">${esc(String(score))} &#9733;</span>` : ""}
      <span>${esc(String(year))}</span>
      <span>${esc(String(episodes))} eps</span>
      <span>${esc(status)}</span>
      ${studios ? `<span>${esc(studios)}</span>` : ""}
    </div>
    <div class="anime-tags" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">
      ${(data.genres || []).concat(data.demographics || []).concat(data.themes || []).map((g) =>
        `<span class="chip chip-small">${esc(g.name)}</span>`
      ).join("")}
    </div>
    <div class="play-section">
      <button class="btn btn-play" id="anime-detail-play">&#9654; Assistir no Sunny</button>
    </div>
    <div class="overview">${esc(synopsis)}</div>
    ${rating ? `<p style="color:#666;font-size:12px;margin-top:8px;">Classificacao: ${esc(rating)}</p>` : ""}
    <div class="similar-row" id="anime-recs"><h3 class="row-title">Recomendados</h3><div class="row-scroll" id="anime-recs-scroll"><div class="loading" style="padding:20px;">Carregando...</div></div></div>
  `;
  body.querySelector("#anime-detail-play").onclick = () => playTitle(title, null, null, true);

  // Load recommendations
  const recs = await api(`/api/anime/recommendations?id=${malId}`);
  const recsScroll = document.getElementById("anime-recs-scroll");
  if (recs.data && recs.data.length > 0) {
    recsScroll.innerHTML = "";
    recs.data.slice(0, 20).forEach((rec) => {
      recsScroll.appendChild(makeAnimeCard(rec));
    });
  } else {
    document.getElementById("anime-recs").style.display = "none";
  }
}

// --- Page loaders ---
// Genre pools for dynamic home — pick random ones each load
const _tvGenres = [
  { id: 10759, name: "Acao e Aventura" },
  { id: 10765, name: "Sci-Fi e Fantasia" },
  { id: 35, name: "Comedia" },
  { id: 16, name: "Animacao" },
  { id: 18, name: "Drama" },
  { id: 80, name: "Crime" },
  { id: 9648, name: "Misterio" },
  { id: 10768, name: "Guerra e Politica" },
  { id: 99, name: "Documentario" },
  { id: 10751, name: "Familia" },
];
const _movieGenres = [
  { id: 28, name: "Acao" },
  { id: 878, name: "Ficcao Cientifica" },
  { id: 35, name: "Comedia" },
  { id: 27, name: "Terror" },
  { id: 53, name: "Suspense" },
  { id: 12, name: "Aventura" },
  { id: 16, name: "Animacao" },
  { id: 10749, name: "Romance" },
  { id: 80, name: "Crime" },
  { id: 99, name: "Documentario" },
  { id: 14, name: "Fantasia" },
  { id: 36, name: "Historia" },
];

function _pickRandom(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

function _randomPage() {
  // Pages 1-3 for variety
  return Math.floor(Math.random() * 3) + 1;
}

async function loadHome() {
  const main = document.getElementById("main-content");
  _shownIds = new Set();

  // Pick random genres each load (3 TV + 2 movie)
  const tvPicks = _pickRandom(_tvGenres, 3);
  const moviePicks = _pickRandom(_movieGenres, 2);

  const [history, trending] = await Promise.all([
    api("/api/history"),
    api(`/api/trending?type=all&window=week&page=${_randomPage()}`),
  ]);

  main.innerHTML = "";

  // Hero from trending — pick a random one with backdrop
  if (trending.results && trending.results.length > 0) {
    const candidates = trending.results.filter((i) => i.backdrop_path && i.overview);
    const heroItem = candidates.length > 0
      ? candidates[Math.floor(Math.random() * Math.min(5, candidates.length))]
      : trending.results[0];
    main.appendChild(makeHero(heroItem));
  }

  // Continue watching (fetch posters in parallel)
  if (history.length > 0) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = '<h3 class="row-title">Continuar Assistindo</h3>';
    const scroll = document.createElement("div");
    scroll.className = "row-scroll";

    const searchResults = await Promise.all(
      history.map((h) => api(`/api/search?q=${encodeURIComponent(h.title)}&type=multi`))
    );
    history.forEach((h, i) => {
      const sr = searchResults[i];
      let card;
      if (sr.results && sr.results.length > 0) {
        const match = sr.results[0];
        card = makeCard(match);
        const meta = card.querySelector(".card-meta");
        if (meta) meta.innerHTML += ` | S${h.season}E${h.episode}`;
      } else {
        card = makeHistoryCard(h);
      }
      // Add remove button
      const removeBtn = document.createElement("button");
      removeBtn.className = "card-remove";
      removeBtn.innerHTML = "&times;";
      removeBtn.title = "Remover";
      removeBtn.onclick = async (e) => {
        e.stopPropagation();
        await fetch(`/api/history?title=${encodeURIComponent(h.title)}`, { method: "DELETE" });
        card.remove();
      };
      card.style.position = "relative";
      card.appendChild(removeBtn);
      scroll.appendChild(card);
    });

    row.appendChild(scroll);
    main.appendChild(row);
  }

  // Trending
  if (trending.results) {
    main.appendChild(makeRow("Em Alta", trending.results));
  }

  // Load dynamic genre rows in parallel (mixed TV + movies)
  const genreRequests = [
    ...tvPicks.map((g) => ({ ...g, type: "tv", page: _randomPage() })),
    ...moviePicks.map((g) => ({ ...g, type: "movie", page: _randomPage() })),
  ];

  const genreResults = await Promise.all(
    genreRequests.map((g) => api(`/api/discover?type=${g.type}&genre=${g.id}&page=${g.page}`))
  );

  // Shuffle the order so it's not always TV first
  const rowPairs = genreRequests.map((g, i) => ({ genre: g, data: genreResults[i] }));
  rowPairs.sort(() => Math.random() - 0.5);

  for (const { genre, data } of rowPairs) {
    if (data.results && data.results.length > 0) {
      const label = genre.type === "movie" ? `${genre.name} (Filmes)` : genre.name;
      main.appendChild(makeRow(label, data.results, genre.type));
    }
  }

  // Also add a "Top Rated" or "New Releases" row for extra freshness
  const bonusType = Math.random() > 0.5 ? "tv" : "movie";
  const bonusData = await api(`/api/discover?type=${bonusType}&sort=vote_average.desc&vote_count=500&page=${_randomPage()}`);
  if (bonusData.results && bonusData.results.length > 0) {
    const bonusLabel = bonusType === "movie" ? "Filmes Bem Avaliados" : "Series Bem Avaliadas";
    main.appendChild(makeRow(bonusLabel, bonusData.results, bonusType));
  }
}

async function loadAnime(filterGenre = null, sort = null) {
  if (sort !== null) animeSort = sort;
  animeCurrentGenre = filterGenre;
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Carregando...</div>';

  const categories = await api("/api/anime/categories");

  if (filterGenre) {
    await loadAnimeGenrePage(main, categories, filterGenre);
  } else {
    await loadAnimeHome(main, categories);
  }
}

async function loadAnimeHome(main, categories) {
  _shownIds = new Set();

  // Use TMDB for anime home — much better trending/discovery than Jikan
  // Genre 16 = Animation, origin_country=JP = Japanese anime
  const animeBase = "type=tv&genre=16&keyword=210024&origin_country=JP";
  const sortParam = animeSort === "top_rated" ? "vote_average.desc" : "popularity.desc";
  const voteMin = animeSort === "top_rated" ? "&vote_count=200" : "";

  const [trending, popular, topRated, newReleases] = await Promise.all([
    api("/api/trending?type=tv&window=week"),
    api(`/api/discover?${animeBase}&sort=${sortParam}${voteMin}`),
    api(`/api/discover?${animeBase}&sort=vote_average.desc&vote_count=500`),
    api(`/api/discover?${animeBase}&sort=first_air_date.desc&vote_count=20`),
  ]);

  main.innerHTML = "";

  // Filter trending to only animation
  const trendingAnime = (trending.results || []).filter(
    (r) => r.genre_ids && r.genre_ids.includes(16) && r.original_language === "ja"
  );

  // Hero from trending anime or popular
  const heroSource = trendingAnime.length > 0 ? trendingAnime : (popular.results || []);
  if (heroSource.length > 0) {
    const candidates = heroSource.filter((i) => i.backdrop_path && i.overview);
    const heroItem = candidates.length > 0
      ? candidates[Math.floor(Math.random() * Math.min(5, candidates.length))]
      : heroSource[0];
    heroItem.media_type = "tv";
    main.appendChild(makeHero(heroItem));
  }

  // Category chips
  main.appendChild(makeAnimeChips(categories, null));

  // Trending anime
  if (trendingAnime.length > 0) {
    trendingAnime.forEach((r) => r.media_type = "tv");
    main.appendChild(makeRow("Animes em Alta", trendingAnime, "tv"));
  }

  // New releases
  if (newReleases.results && newReleases.results.length > 0) {
    main.appendChild(makeRow("Lancamentos Recentes", newReleases.results, "tv"));
  }

  // Popular / Top rated
  if (popular.results && popular.results.length > 0) {
    main.appendChild(makeRow(animeSort === "top_rated" ? "Melhor Avaliados" : "Populares", popular.results, "tv"));
  }

  // Top rated (always show if sorting by popular, for contrast)
  if (animeSort !== "top_rated" && topRated.results && topRated.results.length > 0) {
    main.appendChild(makeRow("Melhor Avaliados", topRated.results, "tv"));
  }

  // Genre-specific rows via TMDB (anime + sub-genre)
  // TMDB TV genre IDs that work well with animation
  const animeSubGenres = [
    { id: "10759", name: "Acao e Aventura" },
    { id: "10765", name: "Sci-Fi e Fantasia" },
    { id: "35", name: "Comedia" },
    { id: "18", name: "Drama" },
    { id: "10749", name: "Romance" },
    { id: "9648", name: "Misterio" },
  ];

  // Load all sub-genre rows in parallel
  const subGenreResults = await Promise.all(
    animeSubGenres.map((g) =>
      api(`/api/discover?type=tv&genre=16,${g.id}&keyword=210024&origin_country=JP&sort=${sortParam}${voteMin}&page=${_randomPage()}`)
    )
  );

  animeSubGenres.forEach((g, i) => {
    if (currentSection !== "anime" || animeCurrentGenre !== null) return;
    if (subGenreResults[i].results && subGenreResults[i].results.length > 0) {
      main.appendChild(makeRow(g.name, subGenreResults[i].results, "tv"));
    }
  });

  // Bonus: Jikan current season for truly "airing now" (one small Jikan call)
  const seasonData = await api("/api/anime/season");
  if (seasonData.data && seasonData.data.length > 0) {
    main.appendChild(makeAnimeRow("No Ar Agora (MAL)", seasonData.data));
  }
}

async function loadAnimeGenrePage(main, categories, genreKey) {
  const catInfo = categories.find((c) => c.id === genreKey);
  const catName = catInfo?.name || genreKey;
  const jikanOrder = animeSort === "top_rated" ? "score" : "popularity";

  // Load first page (min_score=6 filters low-quality, start_date filters very old)
  const p1 = await api(`/api/anime/genre?genre=${genreKey}&page=1&order_by=${jikanOrder}&min_score=6&start_date=2005-01-01`);
  main.innerHTML = "";

  // Hero from genre
  if (p1.data && p1.data.length > 0) {
    const hero = p1.data.find((a) => a.images?.jpg?.large_image_url && a.synopsis) || p1.data[0];
    main.appendChild(makeAnimeHero(hero));
  }

  // Chips
  main.appendChild(makeAnimeChips(categories, genreKey));

  // Title
  const titleEl = document.createElement("div");
  titleEl.className = "section-title";
  titleEl.textContent = catName + (animeSort === "top_rated" ? " - Maior Nota" : "");
  main.appendChild(titleEl);

  // Grid with all results
  const grid = document.createElement("div");
  grid.className = "results-grid";
  grid.id = "anime-genre-grid";
  if (p1.data) {
    p1.data.forEach((item) => grid.appendChild(makeAnimeCard(item)));
  }
  main.appendChild(grid);

  // Load more button
  const hasMore = p1.pagination && p1.pagination.has_next_page;
  if (hasMore) {
    const loadMoreDiv = document.createElement("div");
    loadMoreDiv.id = "anime-load-more";
    loadMoreDiv.style.cssText = "text-align:center;padding:24px;";
    const moreBtn = document.createElement("button");
    moreBtn.className = "btn btn-info";
    moreBtn.textContent = "Carregar Mais";
    moreBtn.onclick = () => loadMoreAnimeGenre(genreKey, 2);
    loadMoreDiv.appendChild(moreBtn);
    main.appendChild(loadMoreDiv);
  }
}

async function loadMoreAnimeGenre(genreKey, page) {
  const btn = document.querySelector("#anime-load-more button");
  if (btn) btn.textContent = "Carregando...";

  const jikanOrder = animeSort === "top_rated" ? "score" : "popularity";
  const data = await api(`/api/anime/genre?genre=${genreKey}&page=${page}&order_by=${jikanOrder}&min_score=6&start_date=2005-01-01`);
  const grid = document.getElementById("anime-genre-grid");
  if (data.data && grid) {
    data.data.forEach((item) => grid.appendChild(makeAnimeCard(item)));
  }

  const loadMoreDiv = document.getElementById("anime-load-more");
  if (data.pagination?.has_next_page && loadMoreDiv) {
    loadMoreDiv.innerHTML = "";
    const nextBtn = document.createElement("button");
    nextBtn.className = "btn btn-info";
    nextBtn.textContent = "Carregar Mais";
    nextBtn.onclick = () => loadMoreAnimeGenre(genreKey, page + 1);
    loadMoreDiv.appendChild(nextBtn);
  } else if (loadMoreDiv) {
    loadMoreDiv.remove();
  }
}

function makeAnimeChips(categories, activeGenre) {
  const chips = document.createElement("div");
  chips.className = "anime-chips";

  const genreArg = activeGenre ? "'" + activeGenre + "'" : "null";

  // Sort buttons + Adult toggle
  chips.innerHTML = `
    <button class="chip ${animeSort === 'popular' ? 'chip-active' : ''}" id="chip-popular">Popular</button>
    <button class="chip ${animeSort === 'top_rated' ? 'chip-active' : ''}" id="chip-toprated">Maior Nota</button>
    <span style="width:1px;height:20px;background:rgba(255,255,255,0.15);margin:0 4px;"></span>
    <button class="chip ${animeAdult ? 'chip-adult-active' : 'chip-adult'}" id="chip-adult">Adulto</button>
    <span style="width:1px;height:20px;background:rgba(255,255,255,0.15);margin:0 4px;"></span>
    <button class="chip ${!activeGenre ? 'chip-active' : ''}" id="chip-all">Todos</button>
  `;
  chips.querySelector("#chip-popular").onclick = () => loadAnime(activeGenre, "popular");
  chips.querySelector("#chip-toprated").onclick = () => loadAnime(activeGenre, "top_rated");
  chips.querySelector("#chip-adult").onclick = () => {
    animeAdult = !animeAdult;
    if (animeAdult) { currentSection = "adult"; loadAdult(); }
    else { currentSection = "anime"; loadAnime(); }
  };
  chips.querySelector("#chip-all").onclick = () => loadAnime(null);

  categories.forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = `chip ${activeGenre === cat.id ? "chip-active" : ""}`;
    btn.textContent = cat.name;
    btn.onclick = () => loadAnime(cat.id);
    chips.appendChild(btn);
  });
  return chips;
}

// TMDB genre IDs
const TV_GENRES = [
  { id: "awards", name: "Premiados" },
  { id: 10759, name: "Acao e Aventura" },
  { id: 16,    name: "Animacao" },
  { id: 35,    name: "Comedia" },
  { id: 80,    name: "Crime" },
  { id: 99,    name: "Documentario" },
  { id: 18,    name: "Drama" },
  { id: 10751, name: "Familia" },
  { id: 9648,  name: "Misterio" },
  { id: 10764, name: "Reality" },
  { id: 10765, name: "Sci-Fi e Fantasia" },
  { id: 10768, name: "Guerra e Politica" },
  { id: 37,    name: "Faroeste" },
];

const MOVIE_GENRES = [
  { id: "awards", name: "Premiados" },
  { id: 28,    name: "Acao" },
  { id: 12,    name: "Aventura" },
  { id: 16,    name: "Animacao" },
  { id: 35,    name: "Comedia" },
  { id: 80,    name: "Crime" },
  { id: 99,    name: "Documentario" },
  { id: 18,    name: "Drama" },
  { id: 10751, name: "Familia" },
  { id: 14,    name: "Fantasia" },
  { id: 36,    name: "Historia" },
  { id: 27,    name: "Horror" },
  { id: 10402, name: "Musica" },
  { id: 9648,  name: "Misterio" },
  { id: 10749, name: "Romance" },
  { id: 878,   name: "Ficcao Cientifica" },
  { id: 53,    name: "Suspense" },
  { id: 10752, name: "Guerra" },
  { id: 37,    name: "Faroeste" },
];

function makeSortChips(mediaType, activeGenre, sortBy, genres, loadFn) {
  const container = document.createElement("div");
  container.className = "anime-chips";

  // Sort toggle
  const popBtn = document.createElement("button");
  popBtn.className = `chip ${sortBy === "popular" ? "chip-active" : ""}`;
  popBtn.textContent = "Popular";
  popBtn.onclick = () => loadFn(activeGenre, "popular");
  container.appendChild(popBtn);

  const rateBtn = document.createElement("button");
  rateBtn.className = `chip ${sortBy === "top_rated" ? "chip-active" : ""}`;
  rateBtn.textContent = "Maior Nota";
  rateBtn.onclick = () => loadFn(activeGenre, "top_rated");
  container.appendChild(rateBtn);

  // Separator
  const sep = document.createElement("span");
  sep.style.cssText = "width:1px;height:20px;background:rgba(255,255,255,0.15);margin:0 4px;";
  container.appendChild(sep);

  // Genre chips
  const allBtn = document.createElement("button");
  allBtn.className = `chip ${!activeGenre ? "chip-active" : ""}`;
  allBtn.textContent = "Todos";
  allBtn.onclick = () => loadFn(null, sortBy);
  container.appendChild(allBtn);

  genres.forEach((g) => {
    const btn = document.createElement("button");
    btn.className = `chip ${activeGenre === g.id ? "chip-active" : ""}`;
    btn.textContent = g.name;
    btn.onclick = () => loadFn(g.id, sortBy);
    container.appendChild(btn);
  });

  return container;
}

let seriesState = { genre: null, sort: "popular" };
let moviesState = { genre: null, sort: "popular" };

async function loadSeries(genre = null, sort = "popular") {
  _shownIds = new Set();
  seriesState = { genre, sort };
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Carregando...</div>';

  const sortParam = sort === "top_rated" ? "vote_average.desc" : "popularity.desc";
  const extraParams = sort === "top_rated" ? "&vote_count=200" : "";
  const genreParam = genre ? `&genre=${genre}` : "";

  const [trending, p1, p2, p3] = await Promise.all([
    api("/api/trending?type=tv&window=week"),
    api(`/api/discover?type=tv&page=1&sort=${sortParam}${genreParam}${extraParams}`),
    api(`/api/discover?type=tv&page=2&sort=${sortParam}${genreParam}${extraParams}`),
    api(`/api/discover?type=tv&page=3&sort=${sortParam}${genreParam}${extraParams}`),
  ]);

  main.innerHTML = "";

  // Hero
  const heroSource = genre ? p1 : trending;
  const heroResults = heroSource.results || [];
  if (heroResults.length > 0) {
    const heroItem = heroResults.find((i) => i.backdrop_path && i.overview) || heroResults[0];
    heroItem.media_type = "tv";
    main.appendChild(makeHero(heroItem));
  }

  // Chips
  main.appendChild(makeSortChips("tv", genre, sort, TV_GENRES, loadSeries));

  if (genre) {
    const genreName = TV_GENRES.find((g) => g.id === genre)?.name || "Series";
    const titleEl = document.createElement("div");
    titleEl.className = "section-title";
    titleEl.textContent = genreName + (sort === "top_rated" ? " - Maior Nota" : "");
    main.appendChild(titleEl);
    const grid = document.createElement("div");
    grid.className = "results-grid";
    const seen = new Set();
    [p1, p2, p3].forEach((p) => {
      (p.results || []).forEach((item) => {
        if (seen.has(item.id)) return;
        seen.add(item.id);
        item.media_type = "tv";
        grid.appendChild(makeCard(item));
      });
    });
    main.appendChild(grid);
  } else {
    const seen = new Set();
    if (!sort || sort === "popular") {
      if (trending.results) {
        trending.results.forEach((i) => seen.add(i.id));
        main.appendChild(makeRow("Series em Alta", trending.results, "tv"));
      }
    }
    if (p1.results) {
      const filtered = p1.results.filter((i) => !seen.has(i.id));
      filtered.forEach((i) => seen.add(i.id));
      if (filtered.length > 0) main.appendChild(makeRow(sort === "top_rated" ? "Melhor Avaliadas" : "Populares", filtered, "tv"));
    }

    // Load genre rows + awards in parallel
    const genreRows = ["awards", 10759, 18, 35, 80, 10765, 9648, 10751, 99, 10768, 37];
    const genreData = await Promise.all(
      genreRows.map((gid) => api(`/api/discover?type=tv&genre=${gid}&sort=${sortParam}${extraParams}`))
    );
    genreRows.forEach((gid, i) => {
      const info = TV_GENRES.find((g) => g.id === gid);
      if (genreData[i].results && genreData[i].results.length > 0 && info) {
        const filtered = genreData[i].results.filter((item) => !seen.has(item.id));
        filtered.forEach((item) => seen.add(item.id));
        if (filtered.length < 3) return;
        const row = makeRow(info.name, filtered, "tv");
        const title = row.querySelector(".row-title");
        title.style.cursor = "pointer";
        title.onclick = () => loadSeries(gid, sort);
        main.appendChild(row);
      }
    });
  }
}

async function loadMovies(genre = null, sort = "popular") {
  _shownIds = new Set();
  moviesState = { genre, sort };
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Carregando...</div>';

  const sortParam = sort === "top_rated" ? "vote_average.desc" : "popularity.desc";
  const extraParams = sort === "top_rated" ? "&vote_count=200" : "";
  const genreParam = genre ? `&genre=${genre}` : "";

  const [trending, p1, p2, p3] = await Promise.all([
    api("/api/trending?type=movie&window=week"),
    api(`/api/discover?type=movie&page=1&sort=${sortParam}${genreParam}${extraParams}`),
    api(`/api/discover?type=movie&page=2&sort=${sortParam}${genreParam}${extraParams}`),
    api(`/api/discover?type=movie&page=3&sort=${sortParam}${genreParam}${extraParams}`),
  ]);

  main.innerHTML = "";

  // Hero
  const heroSource = genre ? p1 : trending;
  const heroResults = heroSource.results || [];
  if (heroResults.length > 0) {
    const heroItem = heroResults.find((i) => i.backdrop_path && i.overview) || heroResults[0];
    heroItem.media_type = "movie";
    main.appendChild(makeHero(heroItem));
  }

  // Chips
  main.appendChild(makeSortChips("movie", genre, sort, MOVIE_GENRES, loadMovies));

  if (genre) {
    const genreName = MOVIE_GENRES.find((g) => g.id === genre)?.name || "Filmes";
    const titleEl = document.createElement("div");
    titleEl.className = "section-title";
    titleEl.textContent = genreName + (sort === "top_rated" ? " - Maior Nota" : "");
    main.appendChild(titleEl);
    const grid = document.createElement("div");
    grid.className = "results-grid";
    const seen = new Set();
    [p1, p2, p3].forEach((p) => {
      (p.results || []).forEach((item) => {
        if (seen.has(item.id)) return;
        seen.add(item.id);
        item.media_type = "movie";
        grid.appendChild(makeCard(item));
      });
    });
    main.appendChild(grid);
  } else {
    const seen = new Set();
    if (!sort || sort === "popular") {
      if (trending.results) {
        trending.results.forEach((i) => seen.add(i.id));
        main.appendChild(makeRow("Filmes em Alta", trending.results, "movie"));
      }
    }
    if (p1.results) {
      const filtered = p1.results.filter((i) => !seen.has(i.id));
      filtered.forEach((i) => seen.add(i.id));
      if (filtered.length > 0) main.appendChild(makeRow(sort === "top_rated" ? "Melhor Avaliados" : "Populares", filtered, "movie"));
    }

    const genreRows = ["awards", 28, 12, 35, 18, 27, 878, 14, 10749, 53, 80, 99, 10752];
    const genreData = await Promise.all(
      genreRows.map((gid) => api(`/api/discover?type=movie&genre=${gid}&sort=${sortParam}${extraParams}`))
    );
    genreRows.forEach((gid, i) => {
      const info = MOVIE_GENRES.find((g) => g.id === gid);
      if (genreData[i].results && genreData[i].results.length > 0 && info) {
        const filtered = genreData[i].results.filter((item) => !seen.has(item.id));
        filtered.forEach((item) => seen.add(item.id));
        if (filtered.length < 3) return;
        const row = makeRow(info.name, filtered, "movie");
        const title = row.querySelector(".row-title");
        title.style.cursor = "pointer";
        title.onclick = () => loadMovies(gid, sort);
        main.appendChild(row);
      }
    });
  }
}

// --- Search ---
async function doSearch(val) {
  const q = (val || document.getElementById("search-input").value).trim();
  if (!q) return;

  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Buscando...</div>';

  const data = await api(`/api/search?q=${encodeURIComponent(q)}&type=multi`);
  main.innerHTML = `<div class="section-title">Resultados para "${esc(q)}"</div>`;

  if (!data.results || data.results.length === 0) {
    main.innerHTML += '<div class="loading" style="padding:40px;">Nenhum resultado encontrado</div>';
    return;
  }

  const grid = document.createElement("div");
  grid.className = "results-grid";
  data.results.forEach((item) => {
    if (item.media_type === "person") return;
    grid.appendChild(makeCard(item));
  });
  main.appendChild(grid);
}

async function searchAndShowDetail(title) {
  const data = await api(`/api/search?q=${encodeURIComponent(title)}&type=multi`);
  if (data.results && data.results.length > 0) {
    const item = data.results[0];
    const type = item.media_type || (item.first_air_date ? "tv" : "movie");
    showDetail(item.id, type);
  }
}

// --- Detail Modal ---
async function showDetail(id, type = "tv") {
  const modal = document.getElementById("detail-modal");
  const backdrop = document.getElementById("detail-backdrop");
  const body = document.getElementById("detail-body");

  modal.classList.remove("hidden");
  body.innerHTML = '<div class="loading">Carregando...</div>';
  backdrop.style.backgroundImage = "";

  const data = await api(`/api/details?id=${id}&type=${type}`);
  if (data.error) {
    body.innerHTML = `<p>${esc(data.error)}</p>`;
    return;
  }

  const title = data.title || data.name;
  const originalTitle = data.original_title || data.original_name || title;
  const year = (data.release_date || data.first_air_date || "").slice(0, 4);
  const rating = data.vote_average ? data.vote_average.toFixed(1) : "";
  const genres = (data.genres || []).map((g) => g.name).join(", ");
  const seasons = data.seasons || [];

  if (data.backdrop_path) {
    backdrop.style.backgroundImage = `url('${BACKDROP}${data.backdrop_path}')`;
  }

  let seasonsHTML = "";
  if (type === "tv" && seasons.length > 0) {
    const realSeasons = seasons.filter((s) => s.season_number > 0);
    if (realSeasons.length > 0) {
      seasonsHTML = `
        <div class="season-selector">
          <select id="season-select">
            ${realSeasons.map((s) => `<option value="${s.season_number}">Temporada ${s.season_number} (${s.episode_count} eps)</option>`).join("")}
          </select>
        </div>
        <div id="episodes-list"><div class="loading">Carregando episodios...</div></div>
      `;
    }
  }

  // Similar/Recommendations
  let similarHTML = "";
  const recs = data.recommendations?.results || data.similar?.results || [];
  if (recs.length > 0) {
    similarHTML = `<div class="similar-row"><h3 class="row-title">Semelhantes</h3><div class="row-scroll" id="similar-scroll"></div></div>`;
  }

  body.innerHTML = `
    <h2>${esc(title)}</h2>
    <div class="meta">
      ${rating ? `<span class="rating">${esc(rating)} &#9733;</span>` : ""}
      <span>${esc(year)}</span>
      ${data.number_of_seasons ? `<span>${data.number_of_seasons} temporada${data.number_of_seasons > 1 ? "s" : ""}</span>` : ""}
      ${data.runtime ? `<span>${data.runtime} min</span>` : ""}
      <span>${esc(genres)}</span>
    </div>
    <div class="play-section">
      <button class="btn btn-play" id="detail-play">&#9654; Assistir no Sunny</button>
    </div>
    <div class="overview">${esc(data.overview || "")}</div>
    ${seasonsHTML}
    ${similarHTML}
  `;
  body.querySelector("#detail-play").onclick = () => playTitle(title, null, null, false, originalTitle, id, type);
  const seasonSelect = body.querySelector("#season-select");
  if (seasonSelect) {
    seasonSelect.onchange = () => loadSeason(id, seasonSelect.value, title, originalTitle, type);
  }

  // Load first season episodes
  if (type === "tv" && seasons.length > 0) {
    const firstReal = seasons.find((s) => s.season_number > 0);
    if (firstReal) loadSeason(id, firstReal.season_number, title, originalTitle, type);
  }

  // Render similar
  if (recs.length > 0) {
    const scroll = document.getElementById("similar-scroll");
    recs.slice(0, 15).forEach((item) => {
      item.media_type = type;
      scroll.appendChild(makeCard(item));
    });
  }
}

async function loadSeason(tvId, seasonNum, showTitle, originalTitle, mediaType) {
  const container = document.getElementById("episodes-list");
  if (!container) return;
  container.innerHTML = '<div class="loading">Carregando episodios...</div>';

  const data = await api(`/api/season?id=${tvId}&season=${seasonNum}`);
  if (!data.episodes || data.episodes.length === 0) {
    container.innerHTML = "<p>Sem episodios disponiveis</p>";
    return;
  }

  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "episodes-grid";

  data.episodes.forEach((ep) => {
    const still = ep.still_path ? STILL + ep.still_path : "";
    const card = document.createElement("div");
    card.className = "episode-card";
    card.onclick = () => playTitle(showTitle, seasonNum, ep.episode_number, false, originalTitle, tvId, mediaType);
    card.innerHTML = `
      ${still ? `<img class="episode-still" src="${esc(still)}" alt="Ep ${ep.episode_number}" loading="lazy">` : `<div class="episode-still" style="display:flex;align-items:center;justify-content:center;color:#555;">${ep.episode_number}</div>`}
      <div class="episode-info">
        <h4><span class="episode-number">${ep.episode_number}.</span> ${esc(ep.name || `Episodio ${ep.episode_number}`)}</h4>
        <p>${esc(ep.overview || "")}</p>
      </div>
    `;
    grid.appendChild(card);
  });
  container.appendChild(grid);
}

function closeDetail() {
  document.getElementById("detail-modal").classList.add("hidden");
}

// --- Play ---
function isRemoteAccess() {
  const host = window.location.hostname;
  return host !== "localhost" && host !== "127.0.0.1" && !host.startsWith("192.168.") && !host.startsWith("10.");
}

function isMobileDevice() {
  return /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

function shouldUseBrowserPlayer() {
  return isMobileDevice() || isRemoteAccess();
}

async function playTitle(title, season, episode, isAnime, originalTitle, tmdbId, mediaType) {
  if (!title) return;
  const body = { title };
  if (season) body.season = season;
  if (episode) body.episode = episode;
  if (isAnime) body.anime = true;
  if (originalTitle && originalTitle !== title) body.original_title = originalTitle;
  if (tmdbId) body.tmdb_id = tmdbId;
  if (mediaType) body.media_type = mediaType;

  if (shouldUseBrowserPlayer()) {
    playInBrowser(body);
  } else {
    const result = await apiPost("/api/play", body);
    if (result.ok) {
      const notif = document.createElement("div");
      notif.style.cssText = "position:fixed;bottom:24px;right:24px;background:#e50914;color:#fff;padding:14px 24px;border-radius:6px;font-size:14px;font-weight:600;z-index:999;";
      notif.textContent = `Abrindo: ${result.cmd}`;
      document.body.appendChild(notif);
      setTimeout(() => notif.remove(), 4000);
    }
  }
}

// Current playback state for episode navigation
let playerState = { title: "", season: null, episode: null, totalEpisodes: 0 };

async function playInBrowser(body) {
  const modal = document.getElementById("player-modal");
  const loading = document.getElementById("player-loading");
  const video = document.getElementById("hls-video");

  modal.classList.remove("hidden");
  loading.style.display = "block";
  loading.textContent = "Buscando titulo...";
  loading.className = "loading";
  video.style.display = "none";
  updatePlayerControls(false);

  // Progress feedback while waiting
  const steps = [
    [2000, "Conectando ao servidor..."],
    [5000, "Obtendo informacoes..."],
    [9000, "Extraindo stream..."],
    [14000, "Decifrando fonte..."],
    [20000, "Aguarde, servidor lento..."],
  ];
  const stepTimers = steps.map(([ms, msg]) =>
    setTimeout(() => { loading.textContent = msg; }, ms)
  );

  let result;
  try {
    result = await apiPost("/api/stream", body);
  } catch (e) {
    stepTimers.forEach(clearTimeout);
    loading.textContent = "Erro de conexao: " + (e.message || e);
    loading.className = "player-error";
    return;
  }
  stepTimers.forEach(clearTimeout);

  if (!result.ok || !result.url) {
    loading.textContent = result.error || "Erro ao extrair stream";
    loading.className = "player-error";
    return;
  }

  // Save state for navigation
  playerState = {
    title: body.title,
    season: result.season || body.season,
    episode: result.episode || body.episode,
    totalEpisodes: result.total_episodes || 0,
  };
  updatePlayerControls(!!playerState.season);

  loading.style.display = "none";
  video.style.display = "block";

  // Use proxy URL to avoid CORS/Referer issues
  const streamUrl = result.proxy_url || result.url;
  startHlsPlayback(video, streamUrl, loading);

  // Show cast/share buttons
  if (result.proxy_url) {
    showCastShareButtons(result.proxy_url);
  }
}

function startHlsPlayback(video, url, loading) {
  if (window._hls) {
    window._hls.destroy();
  }

  if (Hls.isSupported()) {
    const hls = new Hls();
    window._hls = hls;
    hls.loadSource(url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play();
    });
    hls.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) {
        loading.style.display = "block";
        loading.textContent = "Erro ao reproduzir: " + data.type;
        loading.className = "player-error";
        video.style.display = "none";
      }
    });
  } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = url;
    video.play();
  } else {
    loading.style.display = "block";
    loading.textContent = "Seu navegador nao suporta HLS";
    loading.className = "player-error";
  }
}

function updatePlayerControls(showEpisodeNav) {
  let controls = document.getElementById("player-controls");
  if (!controls) return;
  if (showEpisodeNav) {
    const ep = playerState.episode || 1;
    const hasPrev = ep > 1;
    const hasNext = !playerState.totalEpisodes || ep < playerState.totalEpisodes;
    controls.style.display = "flex";
    controls.innerHTML = `
      <button class="btn btn-info" ${hasPrev ? "" : "disabled"} onclick="playEpisode(${ep - 1})">&#9664; Anterior</button>
      <span style="color:#fff;font-size:14px;">S${playerState.season} E${ep}</span>
      <button class="btn btn-play" ${hasNext ? "" : "disabled"} onclick="playEpisode(${ep + 1})">Proximo &#9654;</button>
    `;
  } else {
    if (controls) controls.style.display = "none";
  }
}

function playEpisode(epNum) {
  if (epNum < 1) return;
  playInBrowser({
    title: playerState.title,
    season: playerState.season,
    episode: epNum,
  });
}

function closePlayer() {
  const modal = document.getElementById("player-modal");
  const video = document.getElementById("hls-video");
  modal.classList.add("hidden");
  if (window._hls) {
    window._hls.destroy();
    window._hls = null;
  }
  video.pause();
  video.src = "";
  document.getElementById("player-top-controls").style.display = "none";
}

// --- Chromecast / Share ---
let currentStreamProxyUrl = "";

// Initialize Cast SDK
window['__onGCastApiAvailable'] = function(isAvailable) {
  if (isAvailable) {
    const context = cast.framework.CastContext.getInstance();
    context.setOptions({
      receiverApplicationId: chrome.cast.media.DEFAULT_MEDIA_RECEIVER_APP_ID,
      autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
    });
  }
};

function showCastShareButtons(proxyUrl) {
  currentStreamProxyUrl = window.location.origin + proxyUrl;
  const topControls = document.getElementById("player-top-controls");
  const castBtn = document.getElementById("cast-btn");
  const shareBtn = document.getElementById("share-btn");

  topControls.style.display = "flex";

  // Show cast button if Cast SDK loaded
  if (typeof cast !== "undefined" && cast.framework) {
    castBtn.style.display = "inline-flex";
  }

  // Show share/open button on mobile
  if (navigator.share || isMobileDevice()) {
    shareBtn.style.display = "inline-flex";
  }
}

function castToTV() {
  if (typeof cast === "undefined" || !cast.framework) return;

  const context = cast.framework.CastContext.getInstance();
  context.requestSession().then(() => {
    const session = context.getCurrentSession();
    const mediaInfo = new chrome.cast.media.MediaInfo(currentStreamProxyUrl, "application/x-mpegURL");
    mediaInfo.streamType = chrome.cast.media.StreamType.BUFFERED;
    mediaInfo.metadata = new chrome.cast.media.GenericMediaMetadata();
    mediaInfo.metadata.title = playerState.title || "Sunny";

    const request = new chrome.cast.media.LoadRequest(mediaInfo);
    session.loadMedia(request).then(
      () => {
        const notif = document.createElement("div");
        notif.style.cssText = "position:fixed;bottom:24px;right:24px;background:#46d369;color:#000;padding:14px 24px;border-radius:6px;font-size:14px;font-weight:600;z-index:999;";
        notif.textContent = "Enviado para a TV!";
        document.body.appendChild(notif);
        setTimeout(() => notif.remove(), 3000);
      },
      (err) => {
        console.error("Cast error:", err);
      }
    );
  }).catch((err) => {
    console.log("Cast session error:", err);
  });
}

function shareStream() {
  if (navigator.share) {
    navigator.share({
      title: playerState.title || "Sunny Stream",
      url: currentStreamProxyUrl,
    }).catch(() => {});
  } else {
    // Fallback: copy to clipboard
    navigator.clipboard.writeText(currentStreamProxyUrl).then(() => {
      const notif = document.createElement("div");
      notif.style.cssText = "position:fixed;bottom:24px;right:24px;background:#e50914;color:#fff;padding:14px 24px;border-radius:6px;font-size:14px;font-weight:600;z-index:999;";
      notif.textContent = "Link copiado!";
      document.body.appendChild(notif);
      setTimeout(() => notif.remove(), 3000);
    });
  }
}

// Keyboard shortcut
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDetail();
  if (e.key === "/" && !e.target.closest("input")) {
    e.preventDefault();
    document.getElementById("search-input").focus();
  }
});

// --- Adult Section ---

function makeAdultCard(video) {
  const div = document.createElement("div");
  div.className = "card";
  div.onclick = () => showAdultDetail(video.slug);
  div.innerHTML = `
    ${video.poster_url ? `<img src="${esc(video.poster_url)}" alt="${esc(video.name)}" loading="lazy">` : `<div style="width:100%;height:278px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;">${esc(video.name)}</div>`}
    <div class="card-info">
      <div class="card-title">${esc(video.name)}</div>
      <div class="card-meta">${video.views ? (video.views > 1000000 ? (video.views / 1000000).toFixed(1) + "M" : Math.floor(video.views / 1000) + "K") + " views" : ""}</div>
    </div>
  `;
  return div;
}

function makeAdultRow(title, videos) {
  const section = document.createElement("div");
  section.className = "row";
  section.innerHTML = `<h3 class="row-title">${esc(title)}</h3>`;
  const scroll = document.createElement("div");
  scroll.className = "row-scroll";
  videos.forEach((v) => scroll.appendChild(makeAdultCard(v)));
  section.appendChild(scroll);
  return section;
}

async function loadAdult(activeTag = null) {
  const main = document.getElementById("main-content");
  main.innerHTML = '<div class="loading">Carregando...</div>';

  if (activeTag) {
    await loadAdultTag(main, activeTag);
    return;
  }

  const [trending, newest, popular, topRated, tags] = await Promise.all([
    api("/api/adult/trending"),
    api("/api/adult/new"),
    api("/api/adult/popular"),
    api("/api/adult/top"),
    api("/api/adult/tags"),
  ]);

  main.innerHTML = "";

  // Back to anime + tag chips
  const chips = document.createElement("div");
  chips.className = "anime-chips";
  const backBtn = document.createElement("button");
  backBtn.className = "chip chip-adult-active";
  backBtn.textContent = "Adulto";
  backBtn.onclick = () => { animeAdult = false; currentSection = "anime"; navigate("anime"); };
  chips.appendChild(backBtn);
  if (Array.isArray(tags)) {
    const sep = document.createElement("span");
    sep.style.cssText = "width:1px;height:20px;background:rgba(255,255,255,0.15);margin:0 4px;";
    chips.appendChild(sep);
    const allBtn = document.createElement("button");
    allBtn.className = `chip ${!activeTag ? "chip-active" : ""}`;
    allBtn.textContent = "Todos";
    allBtn.onclick = () => loadAdult();
    chips.appendChild(allBtn);
    tags.forEach((tag) => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = tag;
      btn.onclick = () => loadAdult(tag);
      chips.appendChild(btn);
    });
  }
  main.appendChild(chips);

  // Hero from trending
  if (Array.isArray(trending) && trending.length > 0) {
    const hero = trending[0];
    const heroDiv = document.createElement("div");
    heroDiv.className = "hero";
    heroDiv.innerHTML = `
      <div class="hero-bg" style="background-image:url('${esc(hero.cover_url || hero.poster_url)}')"></div>
      <div class="hero-info">
        <h2>${esc(hero.name)}</h2>
        <div class="hero-buttons">
          <button class="btn btn-play" id="ahero-play">&#9654; Assistir</button>
          <button class="btn btn-info" id="ahero-info">&#9432; Detalhes</button>
        </div>
      </div>
    `;
    heroDiv.querySelector("#ahero-play").onclick = () => playAdult(hero.slug);
    heroDiv.querySelector("#ahero-info").onclick = () => showAdultDetail(hero.slug);
    main.appendChild(heroDiv);
  }

  if (Array.isArray(trending) && trending.length > 0) {
    main.appendChild(makeAdultRow("Em Alta", trending));
  }
  if (Array.isArray(newest) && newest.length > 0) {
    main.appendChild(makeAdultRow("Novos", newest));
  }
  if (Array.isArray(popular) && popular.length > 0) {
    main.appendChild(makeAdultRow("Mais Vistos", popular));
  }
  if (Array.isArray(topRated) && topRated.length > 0) {
    main.appendChild(makeAdultRow("Mais Curtidos", topRated));
  }
}

async function loadAdultTag(main, tag) {
  const [videos, tags] = await Promise.all([
    api(`/api/adult/tag?tag=${encodeURIComponent(tag)}`),
    api("/api/adult/tags"),
  ]);

  main.innerHTML = "";

  // Back to anime + tag chips
  const chips = document.createElement("div");
  chips.className = "anime-chips";
  const backBtn = document.createElement("button");
  backBtn.className = "chip chip-adult-active";
  backBtn.textContent = "Adulto";
  backBtn.onclick = () => { animeAdult = false; currentSection = "anime"; navigate("anime"); };
  chips.appendChild(backBtn);
  const sep = document.createElement("span");
  sep.style.cssText = "width:1px;height:20px;background:rgba(255,255,255,0.15);margin:0 4px;";
  chips.appendChild(sep);
  if (Array.isArray(tags)) {
    const allBtn = document.createElement("button");
    allBtn.className = "chip";
    allBtn.textContent = "Todos";
    allBtn.onclick = () => loadAdult();
    chips.appendChild(allBtn);
    tags.forEach((t) => {
      const btn = document.createElement("button");
      btn.className = `chip ${t === tag ? "chip-active" : ""}`;
      btn.textContent = t;
      btn.onclick = () => loadAdult(t);
      chips.appendChild(btn);
    });
  }
  main.appendChild(chips);

  const titleEl = document.createElement("div");
  titleEl.className = "section-title";
  titleEl.textContent = tag.charAt(0).toUpperCase() + tag.slice(1);
  main.appendChild(titleEl);

  const grid = document.createElement("div");
  grid.className = "results-grid";
  if (Array.isArray(videos)) {
    videos.forEach((v) => grid.appendChild(makeAdultCard(v)));
  }
  main.appendChild(grid);
}

async function showAdultDetail(slug) {
  const modal = document.getElementById("detail-modal");
  const backdrop = document.getElementById("detail-backdrop");
  const body = document.getElementById("detail-body");

  modal.classList.remove("hidden");
  body.innerHTML = '<div class="loading">Carregando...</div>';
  backdrop.style.backgroundImage = "";

  const data = await api(`/api/adult/video?slug=${encodeURIComponent(slug)}`);
  if (data.error) {
    body.innerHTML = `<p>${esc(data.error)}</p>`;
    return;
  }

  if (data.cover_url) {
    backdrop.style.backgroundImage = `url('${esc(data.cover_url)}')`;
  }

  const duration = data.duration_in_ms ? Math.round(data.duration_in_ms / 60000) + " min" : "";
  const tagsHtml = (data.tags || []).map((t) => `<span class="chip chip-small">${esc(t)}</span>`).join("");

  let franchiseHtml = "";
  if (data.franchise_videos && data.franchise_videos.length > 1) {
    franchiseHtml = `<div class="similar-row"><h3 class="row-title">${esc(data.franchise)}</h3><div class="row-scroll" id="adult-franchise-scroll"></div></div>`;
  }

  let nextHtml = "";
  if (data.next_video) {
    nextHtml = `<div style="margin-top:16px;"><span style="color:#888;">Proximo:</span> <a href="#" id="adult-next" style="color:#e74c3c;">${esc(data.next_video.name)}</a></div>`;
  }

  body.innerHTML = `
    <h2>${esc(data.name)}</h2>
    <div class="meta">
      ${duration ? `<span>${esc(duration)}</span>` : ""}
      ${data.brand ? `<span>${esc(data.brand)}</span>` : ""}
      <span>${data.is_censored ? "Censurado" : "Sem censura"}</span>
      <span>${(data.views || 0).toLocaleString()} views</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">${tagsHtml}</div>
    <div class="play-section">
      <button class="btn btn-play" id="adult-play">&#9654; Assistir</button>
    </div>
    <div class="overview">${esc(data.description || "")}</div>
    ${nextHtml}
    ${franchiseHtml}
  `;

  body.querySelector("#adult-play").onclick = () => playAdult(slug);

  if (data.next_video) {
    body.querySelector("#adult-next").onclick = (e) => {
      e.preventDefault();
      showAdultDetail(data.next_video.slug);
    };
  }

  if (data.franchise_videos && data.franchise_videos.length > 1) {
    const scroll = document.getElementById("adult-franchise-scroll");
    data.franchise_videos.forEach((fv) => scroll.appendChild(makeAdultCard(fv)));
  }
}

function playAdult(slug) {
  window.open(`https://hanime.tv/videos/hentai/${encodeURIComponent(slug)}`, "_blank");
}

init();
