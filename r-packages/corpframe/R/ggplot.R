# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

#' @keywords internal
.render_framed <- function(plot, params) {
  tmp_in <- tempfile(fileext = ".png")
  on.exit(unlink(tmp_in), add = TRUE)

  width <- params$width %||% 8
  height <- params$height %||% 5
  dpi <- params$dpi %||% 300L

  ggplot2::ggsave(tmp_in, plot = plot, width = width, height = height,
                  dpi = dpi, device = "png")

  png_bytes <- readBin(tmp_in, "raw", file.info(tmp_in)$size)

  framed <- apply_frame(
    png_bytes,
    title = params$title %||% "",
    subtitle = params$subtitle %||% "",
    footnotes = params$footnotes %||% "",
    sources = params$sources %||% "",
    dpi = dpi,
    python = params$python
  )

  tmp_out <- tempfile(fileext = ".png")
  writeBin(framed, tmp_out)

  if (requireNamespace("png", quietly = TRUE)) {
    img <- png::readPNG(tmp_out)
    grid::grid.newpage()
    grid::grid.raster(img)
  } else {
    # Fallback: base64-encode and display in RStudio Viewer
    tmp_b64 <- tempfile(fileext = ".b64")
    on.exit(unlink(tmp_b64), add = TRUE)
    system2("base64", c("-i", shQuote(tmp_out), "-o", shQuote(tmp_b64)))
    b64 <- paste(readLines(tmp_b64, warn = FALSE), collapse = "")

    tmp_html <- tempfile(fileext = ".html")
    writeLines(sprintf(
      '<html><body style="margin:0;background:#fff"><img src="data:image/png;base64,%s" style="max-width:100%%"></body></html>',
      b64
    ), tmp_html)
    viewer <- getOption("viewer", utils::browseURL)
    viewer(tmp_html)
  }
}


#' Add a corporate frame to a ggplot
#'
#' Add with \code{+} to any ggplot. The frame is applied at print time,
#' so position in the pipeline doesn't matter. Works with \code{print()},
#' \code{ggsave()}, and RStudio display.
#'
#' Title and subtitle are taken from \code{labs()} by default. If set in
#' both \code{labs()} and \code{corporate_frame()}, both render (with a warning).
#'
#' @param title Header title (NULL = use \code{labs(title)}).
#' @param subtitle Header subtitle (NULL = use \code{labs(subtitle)}).
#' @param footnotes Footer text, left-aligned.
#' @param sources Footer text, right-aligned.
#' @param width Plot width in inches.
#' @param height Plot height in inches.
#' @param dpi Resolution in DPI.
#' @param python Path to Python (NULL for auto-detect).
#' @return Object to add to a ggplot with \code{+}.
#'
#' @examples
#' \dontrun{
#' library(ggplot2)
#'
#' # Title from labs():
#' ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   labs(title = "Weight vs MPG") +
#'   corporate_frame()
#'
#' # Title set directly:
#' ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   corporate_frame(title = "Weight vs MPG")
#'
#' # Save to file:
#' p <- ggplot(mtcars, aes(wt, mpg)) + geom_point() +
#'   corporate_frame(title = "Weight vs MPG")
#' ggsave("chart.png", p)
#' }
#' @export
corporate_frame <- function(title = NULL,
                            subtitle = NULL,
                            footnotes = "",
                            sources = "",
                            width = 8,
                            height = 5,
                            dpi = 300L,
                            python = NULL) {
  structure(
    list(title = title, subtitle = subtitle, footnotes = footnotes,
         sources = sources, width = width, height = height,
         dpi = dpi, python = python),
    class = "corporate_frame_params"
  )
}


#' @export
ggplot_add.corporate_frame_params <- function(object, plot, object_name) {
  attr(plot, "corporate_frame") <- object
  class(plot) <- c("corporate_framed_gg", class(plot))
  # S7 revalidation so RStudio's Environment pane recognizes the object
  # (see _notes.md for details)
  S7::validate(plot)
  plot
}


#' @export
print.corporate_framed_gg <- function(x, ...) {
  params <- attr(x, "corporate_frame")

  class(x) <- setdiff(class(x), "corporate_framed_gg")
  attr(x, "corporate_frame") <- NULL

  if (is.null(params$title)) {
    params$title <- x$labels$title %||% ""
    x$labels$title <- NULL
  } else if (!is.null(x$labels$title)) {
    warning("Both labs(title) and corporate_frame(title) are set; ",
            "both will be rendered.", call. = FALSE)
  }
  if (is.null(params$subtitle)) {
    params$subtitle <- x$labels$subtitle %||% ""
    x$labels$subtitle <- NULL
  } else if (!is.null(x$labels$subtitle)) {
    warning("Both labs(subtitle) and corporate_frame(subtitle) are set; ",
            "both will be rendered.", call. = FALSE)
  }

  .render_framed(x, params)

  invisible(x)
}
