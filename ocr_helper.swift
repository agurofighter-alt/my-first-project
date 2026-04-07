#!/usr/bin/env swift
// ocr_helper.swift — macOS Vision OCR (Japanese + English)
// Usage:
//   ocr_helper <image_path>           — OCR a single image, print text to stdout
//   ocr_helper --pdf <output> <img>…  — Create PDF from images (25-page chunks merged)

import Foundation
import Vision
import AppKit
import PDFKit

// MARK: - OCR

struct OCRResult {
    let text: String
    let x: CGFloat
    let y: CGFloat
}

func performOCR(imagePath: String) -> String {
    guard let image = NSImage(contentsOfFile: imagePath),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        fputs("Error: Cannot load image: \(imagePath)\n", stderr)
        return ""
    }

    let semaphore = DispatchSemaphore(value: 0)
    var results: [OCRResult] = []

    let request = VNRecognizeTextRequest { request, error in
        defer { semaphore.signal() }
        if let error = error {
            fputs("OCR error: \(error.localizedDescription)\n", stderr)
            return
        }
        guard let observations = request.results as? [VNRecognizedTextObservation] else { return }

        for observation in observations {
            guard let candidate = observation.topCandidates(1).first else { continue }
            let boundingBox = observation.boundingBox
            // Y→X sort: use negative Y (top-first) then X (left-first)
            results.append(OCRResult(
                text: candidate.string,
                x: boundingBox.origin.x,
                y: boundingBox.origin.y
            ))
        }
    }

    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ja", "en"]
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        fputs("Vision handler error: \(error.localizedDescription)\n", stderr)
        return ""
    }

    semaphore.wait()

    // Sort by Y (top to bottom, note: Vision Y is bottom-up so invert) then X (left to right)
    results.sort { a, b in
        let yA = 1.0 - a.y
        let yB = 1.0 - b.y
        let yThreshold: CGFloat = 0.02  // Lines within 2% are same row
        if abs(yA - yB) > yThreshold {
            return yA < yB
        }
        return a.x < b.x
    }

    return results.map { $0.text }.joined(separator: "\n")
}

// MARK: - PDF Generation

func createPDF(outputPath: String, imagePaths: [String]) -> Bool {
    let chunkSize = 25
    var tempPDFs: [String] = []

    // Process in 25-page chunks
    let chunks = stride(from: 0, to: imagePaths.count, by: chunkSize).map {
        Array(imagePaths[$0..<min($0 + chunkSize, imagePaths.count)])
    }

    for (index, chunk) in chunks.enumerated() {
        let tempPath = NSTemporaryDirectory() + "kindle_chunk_\(index).pdf"
        let pdfDoc = PDFDocument()

        for imagePath in chunk {
            guard let image = NSImage(contentsOfFile: imagePath) else {
                fputs("Warning: Cannot load image for PDF: \(imagePath)\n", stderr)
                continue
            }
            if let page = PDFPage(image: image) {
                pdfDoc.insert(page, at: pdfDoc.pageCount)
            }
        }

        guard pdfDoc.write(toFile: tempPath) else {
            fputs("Error: Cannot write chunk PDF: \(tempPath)\n", stderr)
            return false
        }
        tempPDFs.append(tempPath)
    }

    // Merge chunks if multiple
    if tempPDFs.count == 1 {
        let fm = FileManager.default
        try? fm.removeItem(atPath: outputPath)
        do {
            try fm.moveItem(atPath: tempPDFs[0], toPath: outputPath)
        } catch {
            fputs("Error: Cannot move PDF: \(error.localizedDescription)\n", stderr)
            return false
        }
    } else {
        guard let mergedPDF = PDFDocument() as PDFDocument? else { return false }
        for tempPath in tempPDFs {
            guard let chunk = PDFDocument(url: URL(fileURLWithPath: tempPath)) else {
                fputs("Error: Cannot read chunk for merge: \(tempPath)\n", stderr)
                return false
            }
            for i in 0..<chunk.pageCount {
                if let page = chunk.page(at: i) {
                    mergedPDF.insert(page, at: mergedPDF.pageCount)
                }
            }
        }
        guard mergedPDF.write(toFile: outputPath) else {
            fputs("Error: Cannot write merged PDF\n", stderr)
            return false
        }
    }

    // Clean up temp files
    let fm = FileManager.default
    for tempPath in tempPDFs {
        try? fm.removeItem(atPath: tempPath)
    }

    print("PDF created: \(outputPath) (\(imagePaths.count) pages)")
    return true
}

// MARK: - Main

let args = CommandLine.arguments

if args.count < 2 {
    fputs("Usage:\n", stderr)
    fputs("  ocr_helper <image_path>           — OCR a single image\n", stderr)
    fputs("  ocr_helper --pdf <output> <img>…  — Create PDF from images\n", stderr)
    exit(1)
}

if args[1] == "--pdf" {
    guard args.count >= 4 else {
        fputs("Usage: ocr_helper --pdf <output.pdf> <image1> [image2] ...\n", stderr)
        exit(1)
    }
    let outputPath = args[2]
    let imagePaths = Array(args[3...])
    let success = createPDF(outputPath: outputPath, imagePaths: imagePaths.map { String($0) })
    exit(success ? 0 : 1)
} else {
    let imagePath = args[1]
    let text = performOCR(imagePath: imagePath)
    print(text)
}
