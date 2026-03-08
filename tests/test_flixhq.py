"""Tests for provider.flixhq parsing (mocked HTTP)."""

import unittest
from unittest.mock import patch


MOCK_SEARCH_HTML = '''
<div class="film_list-wrap">
  <div class="flw-item">
    <div class="film-detail">
      <h3 class="film-name"><a href="/tv/breaking-bad-12345" title="Breaking Bad">Breaking Bad</a></h3>
    </div>
  </div>
  <div class="flw-item">
    <div class="film-detail">
      <h3 class="film-name"><a href="/movie/el-camino-67890" title="El Camino">El Camino</a></h3>
    </div>
  </div>
</div>
'''

MOCK_SEASONS_HTML = '''
<div class="ss-list">
  <a data-id="1001">Season 1</a>
  <a data-id="1002">Season 2</a>
</div>
'''

MOCK_EPISODES_HTML = '''
<div class="nav-item">
  <a data-id="2001" title="Pilot Episode">Pilot Episode</a>
  <a data-id="2002" title="Episode 2">Episode 2</a>
</div>
'''

MOCK_SERVERS_HTML = '''
<div class="server-item">
  <a data-id="3001"><span>Vidcloud</span></a>
  <a data-id="3002"><span>UpCloud</span></a>
</div>
'''


class TestFlixHQSearch(unittest.TestCase):
    @patch("provider.flixhq.get", return_value=MOCK_SEARCH_HTML)
    def test_parse_search_results(self, mock_get):
        from provider.flixhq import search
        results = search("breaking bad")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Breaking Bad")
        self.assertEqual(results[0]["type"], "series")
        self.assertTrue(results[0]["url"].endswith("/tv/breaking-bad-12345"))
        self.assertEqual(results[1]["title"], "El Camino")
        self.assertEqual(results[1]["type"], "movie")

    @patch("provider.flixhq.get", return_value="<html>empty</html>")
    def test_no_results(self, mock_get):
        from provider.flixhq import search
        results = search("nonexistent_movie_xyz")
        self.assertEqual(results, [])


class TestFlixHQSeasons(unittest.TestCase):
    @patch("provider.flixhq.get", return_value=MOCK_SEASONS_HTML)
    def test_parse_seasons(self, mock_get):
        from provider.flixhq import get_seasons
        seasons = get_seasons("123")
        self.assertEqual(len(seasons), 2)
        self.assertEqual(seasons[0]["id"], "1001")
        self.assertEqual(seasons[0]["name"], "Season 1")


class TestFlixHQEpisodes(unittest.TestCase):
    @patch("provider.flixhq.get", return_value=MOCK_EPISODES_HTML)
    def test_parse_episodes(self, mock_get):
        from provider.flixhq import get_episodes
        eps = get_episodes("1001")
        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0]["id"], "2001")
        self.assertEqual(eps[0]["name"], "Pilot Episode")


class TestFlixHQServers(unittest.TestCase):
    @patch("provider.flixhq.get", return_value=MOCK_SERVERS_HTML)
    def test_parse_servers(self, mock_get):
        from provider.flixhq import get_servers
        servers = get_servers("2001")
        self.assertEqual(len(servers), 2)
        self.assertEqual(servers[0]["name"], "Vidcloud")
        self.assertEqual(servers[1]["name"], "UpCloud")


class TestFlixHQGetLink(unittest.TestCase):
    @patch("provider.flixhq.get_json", return_value={"link": "https://megacloud.tv/embed/abc123"})
    def test_get_link(self, mock_get_json):
        from provider.flixhq import get_link
        link = get_link("3001")
        self.assertEqual(link, "https://megacloud.tv/embed/abc123")

    @patch("provider.flixhq.get_json", return_value={})
    def test_get_link_empty(self, mock_get_json):
        from provider.flixhq import get_link
        link = get_link("9999")
        self.assertEqual(link, "")


if __name__ == "__main__":
    unittest.main()
