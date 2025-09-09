param(
  [int]$Port = 3500
)

& waitress-serve --listen "0.0.0.0:$Port" ytanalyzer.webapp.app:create_app

