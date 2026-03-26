# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' Find a Python executable with corpframe installed
#'
#' Resolution order:
#' \enumerate{
#'   \item Explicit \code{python} argument
#'   \item \code{options(corpframe.python = ...)}
#'   \item \code{CORPFRAME_PYTHON} environment variable
#'   \item reticulate's Python (if installed)
#'   \item Common system paths and \code{which}
#' }
#'
#' @param python Explicit path, or NULL for auto-detection.
#' @return Path to the Python executable.
#' @export
find_python <- function(python = NULL) {
  if (!is.null(python)) {
    if (!file.exists(python)) stop("Python not found at: ", python)
    return(python)
  }

  opt_python <- getOption("corpframe.python", default = "")
  if (nzchar(opt_python)) {
    if (!file.exists(opt_python)) {
      stop("options(corpframe.python) is set to '", opt_python, "' but file not found")
    }
    return(opt_python)
  }

  env_python <- Sys.getenv("CORPFRAME_PYTHON", "")
  if (nzchar(env_python)) {
    if (!file.exists(env_python)) {
      stop("CORPFRAME_PYTHON is set to '", env_python, "' but file not found")
    }
    return(env_python)
  }

  if (requireNamespace("reticulate", quietly = TRUE)) {
    tryCatch({
      ret_python <- reticulate::py_config()$python
      if (!is.null(ret_python) && nzchar(ret_python) && file.exists(ret_python)) {
        return(ret_python)
      }
    }, error = function(e) NULL)
  }

  common_paths <- c(
    "/usr/local/bin/python3",
    "/usr/bin/python3",
    "/opt/homebrew/bin/python3",
    Sys.which("python3"),
    Sys.which("python")
  )
  for (path in common_paths) {
    if (nzchar(path) && file.exists(path)) {
      return(path)
    }
  }

  for (cmd in c("python3", "python")) {
    path <- system2("which", cmd, stdout = TRUE, stderr = FALSE)
    if (length(path) > 0 && nzchar(path) && file.exists(path)) {
      return(path)
    }
  }

  stop(
    "No Python found. Options:\n",
    "  - Set options(corpframe.python = '/path/to/python')\n",
    "  - Set CORPFRAME_PYTHON env var\n",
    "  - Install Python 3 with corpframe: pip install corpframe\n",
    "  - Pass python argument directly: apply_frame(..., python = '/path/to/python')"
  )
}
