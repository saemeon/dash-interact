# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

.check_shiny <- function() {
  if (!requireNamespace("shiny", quietly = TRUE)) {
    stop("Package 'shiny' is required. Install with install.packages('shiny')")
  }
}

.check_shinycapture <- function() {
  if (!requireNamespace("shinycapture", quietly = TRUE)) {
    stop("Package 'shinycapture' is required. Install from r-packages/shinycapture.")
  }
}

.check_jsonlite <- function() {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Package 'jsonlite' is required. Install with install.packages('jsonlite')")
  }
}


.show_corporate_modal <- function(raw_bytes, title, subtitle, footnotes, sources,
                                   dpi, python, prefix, ns, input, output,
                                   raw_rv, framed_rv, filename) {
  download_id <- paste0(prefix, "dl")
  regenerate_id <- paste0(prefix, "regen")
  title_id <- paste0(prefix, "title")
  subtitle_id <- paste0(prefix, "subtitle")
  footnotes_id <- paste0(prefix, "footnotes")
  sources_id <- paste0(prefix, "sources")

  raw_rv(raw_bytes)

  framed <- apply_frame(
    raw_bytes,
    title = title, subtitle = subtitle,
    footnotes = footnotes, sources = sources,
    dpi = dpi, python = python
  )
  framed_rv(framed)

  .reframe <- function() {
    apply_frame(
      raw_rv(),
      title = input[[title_id]] %||% title,
      subtitle = input[[subtitle_id]] %||% subtitle,
      footnotes = input[[footnotes_id]] %||% footnotes,
      sources = input[[sources_id]] %||% sources,
      dpi = dpi, python = python
    )
  }

  shiny::showModal(shiny::modalDialog(
    title = "Corporate Export",
    size = "l",
    easyClose = TRUE,
    shiny::fluidRow(
      shiny::column(4,
        shiny::textInput(ns(title_id), "Title", value = title),
        shiny::textInput(ns(subtitle_id), "Subtitle", value = subtitle),
        shiny::textInput(ns(footnotes_id), "Footnotes", value = footnotes),
        shiny::textInput(ns(sources_id), "Sources", value = sources),
        shiny::actionButton(ns(regenerate_id), "Update Preview")
      ),
      shiny::column(8,
        shiny::tags$div(
          style = "text-align: center;",
          shiny::imageOutput(ns(paste0(prefix, "preview")),
                             height = "auto")
        )
      )
    ),
    footer = shiny::tagList(
      shiny::downloadButton(ns(download_id), "Download"),
      shiny::modalButton("Close")
    )
  ))

  output[[paste0(prefix, "preview")]] <- shiny::renderImage({
    shiny::req(framed_rv())
    tmp <- tempfile(fileext = ".png")
    writeBin(framed_rv(), tmp)
    list(src = tmp, contentType = "image/png", width = "100%",
         alt = "Corporate framed chart")
  }, deleteFile = TRUE)

  shiny::observeEvent(input[[regenerate_id]], {
    shiny::req(raw_rv())
    framed_rv(.reframe())
  }, ignoreInit = TRUE)

  shiny::observeEvent(
    shiny::debounce(shiny::reactive({
      list(
        input[[title_id]],
        input[[subtitle_id]],
        input[[footnotes_id]],
        input[[sources_id]]
      )
    }), millis = 500)(),
    {
      shiny::req(raw_rv())
      framed_rv(.reframe())
    },
    ignoreInit = TRUE
  )

  output[[download_id]] <- shiny::downloadHandler(
    filename = function() filename,
    content = function(file) {
      shiny::req(raw_rv())
      writeBin(.reframe(), file)
    }
  )
}


#' Corporate export for Plotly charts in Shiny
#'
#' Captures a Plotly output via shinycapture, opens a modal with editable
#' frame text, live preview, and download button. Requires shiny,
#' shinycapture, and jsonlite.
#'
#' @param plot_id Output ID of the \code{plotlyOutput}.
#' @param trigger_id ID of the action button that triggers export.
#' @param title,subtitle,footnotes,sources Default frame text (editable in modal).
#' @param strip_title Remove Plotly title before capture.
#' @param strip_legend Remove legend before capture.
#' @param width,height Capture resolution in pixels.
#' @param dpi Output DPI.
#' @param filename Download filename.
#' @param python Path to Python (NULL for auto-detect).
#' @param session Shiny session.
#' @export
corporate_export_plotly <- function(plot_id,
                                    trigger_id,
                                    title = "",
                                    subtitle = "",
                                    footnotes = "",
                                    sources = "",
                                    strip_title = TRUE,
                                    strip_legend = FALSE,
                                    width = 1200L,
                                    height = 800L,
                                    dpi = 300L,
                                    filename = "chart_corporate.png",
                                    python = NULL,
                                    session = shiny::getDefaultReactiveDomain()) {
  .check_shiny()
  .check_shinycapture()
  .check_jsonlite()

  input <- session$input
  output <- session$output
  ns <- session$ns

  prefix <- paste0(".corpframe_", plot_id, "_")
  capture_input_id <- paste0(".shinycapture.", plot_id)

  raw_rv <- shiny::reactiveVal(NULL)
  framed_rv <- shiny::reactiveVal(NULL)

  shiny::observeEvent(input[[trigger_id]], {
    shinycapture::capture_plotly(
      plot_id,
      strategy = shinycapture::plotly_strategy(
        strip_title = strip_title,
        strip_legend = strip_legend,
        width = width,
        height = height
      ),
      session = session
    )
  })

  shiny::observeEvent(input[[capture_input_id]], {
    raw <- shinycapture::base64_decode(input[[capture_input_id]])
    .show_corporate_modal(
      raw, title, subtitle, footnotes, sources,
      dpi, python, prefix, ns, input, output,
      raw_rv, framed_rv, filename
    )
  })

  invisible(NULL)
}


#' Corporate export for ggplot2 charts in Shiny
#'
#' Renders a ggplot2 reactive server-side, opens a modal with editable
#' frame text, live preview, and download button. Requires shiny and jsonlite.
#'
#' @param plot_reactive Reactive expression returning a ggplot2 object.
#' @param trigger_id ID of the action button that triggers export.
#' @param title,subtitle,footnotes,sources Default frame text (editable in modal).
#' @param width,height Plot dimensions in inches.
#' @param dpi Output DPI.
#' @param filename Download filename.
#' @param python Path to Python (NULL for auto-detect).
#' @param id Unique ID for this export instance (defaults to \code{trigger_id}).
#' @param session Shiny session.
#' @export
corporate_export_gg <- function(plot_reactive,
                                trigger_id,
                                title = "",
                                subtitle = "",
                                footnotes = "",
                                sources = "",
                                width = 8,
                                height = 5,
                                dpi = 300L,
                                filename = "chart_corporate.png",
                                python = NULL,
                                id = trigger_id,
                                session = shiny::getDefaultReactiveDomain()) {
  .check_shiny()
  .check_jsonlite()

  input <- session$input
  output <- session$output
  ns <- session$ns

  prefix <- paste0(".corpframe_gg_", id, "_")

  raw_rv <- shiny::reactiveVal(NULL)
  framed_rv <- shiny::reactiveVal(NULL)

  shiny::observeEvent(input[[trigger_id]], {
    p <- plot_reactive()
    shiny::req(p)

    tmp <- tempfile(fileext = ".png")
    on.exit(unlink(tmp), add = TRUE)
    ggplot2::ggsave(tmp, plot = p, width = width, height = height,
                    dpi = dpi, device = "png")
    raw <- readBin(tmp, "raw", file.info(tmp)$size)

    .show_corporate_modal(
      raw, title, subtitle, footnotes, sources,
      dpi, python, prefix, ns, input, output,
      raw_rv, framed_rv, filename
    )
  })

  invisible(NULL)
}
