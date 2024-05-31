# RAWG to Steam Redirect 💬🚂

> All credit goes to [Toylerrr](https://github.com/Toylerrr) who conceived the idea and initiated this project.

Welcome to the RAWG to Steam Redirect API, a drop-in replacement for `api.rawg.io` that seamlessly redirects requests to the publicly available Steam API.

## Motivation 🚀

This Project was kickstarted by our trusted community member [Toylerrr](https://github.com/toylerrr) to have a quick replacement for the currently unreliable and unmaintained [RAWG.IO](https://rawg.io) API in [GameVault](https://gamevau.lt).

The transition from GameVault to move off of RAWG will likely require a significant amount of time and effort, prompting the need for a swift resolution.

## Features & Supported APIs 🤖

### `/api/games?search=query`

Use this endpoint to search for games.

#### Parameters

- `search`: The query string to search for.
  - in: `query`
  - required: `true`

### `/api/games/:id`

This endpoint retrieves detailed information about a specific game.

#### Parameters

- `id`: The Steam ID of the game to retrieve.
  - in: `path`
  - required: `true`
- `lang`: The language to retrieve data in. Defaults to `english`. Seems to take the english name of the language in lowercase letters. No standard nfortunately. Other examples that worked when testing were: `german`, `italian`
  - in: `query`
  - required: `false`
  - default: `english`

### `/api/games/:id/screenshots`

This endpoint shows screenshots from the selected app ID.

### `/api/stats`

This endpoint returns the number of times each endpoint has been called.

### Response Caching

To reduce the number of API calls `/api/games/:id` responses are cached for 30 days in a local SQLite database.

You will need to mount that file somewhere, so the data can persist.

### Selecting a default language

If you want to set a default language to `german` or `italian` for example for all incoming requests, you can set `R2S_LANG=german` in your environment variables. Default value is `english`.

## Changing the Log Level

You can change the log level by setting the `R2S_LOG_LEVEL` environment variable that controls logging verbosity. See possible values [here](https://docs.python.org/3/library/logging.html#logging-levels). Default value is `20`.

## Limitations ❗

- Maximum of 5 Search Results
- No Pagination
- No sorting, filters, or other advanced features
- Steam could rate-limit your ip address if you make too many requests.
- Developer and Publisher IDs are their hashed names, and not guaranteed to be unique, because Steam does not provide them.
- Release Dates are empty for some languages like `japanese` and `korean`, because the `dateutils.parser` library does not support steams date format.

## Setup ⚙️

### Hosted Instances ☁️

You are free to use a publicly available hosted instance by [Phalcode](https://phalco.de) is available at [https://rawg2steam.phalco.de](https://rawg2steam.phalco.de).

### Setting Up Your Own Instance 🛠️

You can easily set up the API yourself using Docker-Compose. Just add the following to your `docker-compose.yml` file:

```yml
version: "3.8"
services:
  rawg-to-steam-redirect:
    image: phalcode/rawg-to-steam-redirect:latest
    volumes:
      - /path/to/database.sqlite:/usr/src/app/database.sqlite
    ports:
      - "80:9999"
    restart: always
```

## Usage with GameVault 🎲

- Set GameVaults `RAWG_API_URL` environment variable to `https://rawg2steam.phalco.de/api` to redirect the requests to the hosted instance.
- Set GameVaults `RAWG_API_CACHE_DAYS` environment variable to `36500`, so GameVault does not try to search for rawg ids of existing games on steam for the next 100 years.


## Credit 💡

- [Toylerr](https://github.com/Toylerrr) - for the idea and initial development of this project.

- [python-steam-api](https://github.com/deivit24/python-steam-api) - for the Python Steam API Library.

- [steamspy](https://steamspy.com) - for the SteamSpy API used for tags.

- [flask](https://github.com/pallets/flask) - for the framework used in the project.

- [Valve](https://store.steampowered.com/) - for the free to use Steam API.
