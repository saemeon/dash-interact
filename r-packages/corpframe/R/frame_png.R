# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' Apply corporate frame to PNG bytes
#'
#' Wraps a PNG image with a corporate header (title, subtitle) and footer
#' (footnotes, sources) via the Python corpframe CLI. Returns framed PNG bytes.
#'
#' @param png_bytes Raw vector of PNG image data.
#' @param title Header title.
#' @param subtitle Header subtitle.
#' @param footnotes Footer text, left-aligned.
#' @param sources Footer text, right-aligned.
#' @param dpi Output resolution (default 300).
#' @param python Path to Python (NULL for auto-detect via \code{\link{find_python}}).
#' @return Raw vector of the framed PNG.
#'
#' @examples
#' \dontrun{
#' png_bytes <- readBin("chart.png", "raw", file.info("chart.png")$size)
#' framed <- apply_frame(png_bytes, title = "Q4 Revenue")
#' writeBin(framed, "chart_framed.png")
#' }
#' @export
apply_frame <- function(png_bytes,
                        title = "",
                        subtitle = "",
                        footnotes = "",
                        sources = "",
                        dpi = 300L,
                        python = NULL) {
  python <- find_python(python)

  input_file <- tempfile(fileext = ".png")
  output_file <- tempfile(fileext = ".png")
  on.exit(unlink(c(input_file, output_file)), add = TRUE)

  writeBin(png_bytes, input_file)

  cmd <- paste(
    shQuote(python), "-m", "corpframe",
    "--input", shQuote(input_file),
    "--output", shQuote(output_file),
    "--title", shQuote(title),
    "--subtitle", shQuote(subtitle),
    "--footnotes", shQuote(footnotes),
    "--sources", shQuote(sources),
    "--dpi", as.character(dpi)
  )

  result <- system(cmd, intern = TRUE)
  status <- attr(result, "status")

  if (!is.null(status) && status != 0) {
    stop(
      "Corporate frame Python script failed (exit ", status, "):\n",
      paste(result, collapse = "\n")
    )
  }

  if (!file.exists(output_file)) {
    stop("Corporate frame output file not created. Python output:\n",
         paste(result, collapse = "\n"))
  }

  readBin(output_file, "raw", file.info(output_file)$size)
}
