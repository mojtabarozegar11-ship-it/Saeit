// Ramadan War R58 offline launcher: fail-closed SHA-256 runtime verification.
// This is not a code signature or an independent rights certification.
// Copyright (c) 2026 Mojtaba Roozegar; third-party licenses in ASSET-CREDITS.md.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

const expectedRuntimeManifestSHA = "e5408225f55e28c97c785d2a21e8c75d6168fa96bf4791c242c155987167d8b2"
const expectedRuntimeFileCount = 35

type FileRecord struct {
	Bytes  int64  `json:"bytes"`
	SHA256 string `json:"sha256"`
}
type Manifest struct {
	Files map[string]FileRecord `json:"files"`
}

func verifyRuntime(packageRoot string) error {
	data, err := os.ReadFile(filepath.Join(packageRoot, "PACKAGE-MANIFEST.json"))
	if err != nil {
		return fmt.Errorf("read package manifest: %w", err)
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return fmt.Errorf("parse package manifest: %w", err)
	}
	keys := make([]string, 0, expectedRuntimeFileCount)
	for k := range m.Files {
		if strings.HasPrefix(k, "ramadan-war/") {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	if len(keys) != expectedRuntimeFileCount {
		return fmt.Errorf("expected %d game files, found %d", expectedRuntimeFileCount, len(keys))
	}
	h := sha256.New()
	for _, k := range keys {
		v := m.Files[k]
		fmt.Fprintf(h, "%s\t%d\t%s\n", k, v.Bytes, v.SHA256)
	}
	// Strip the final newline to match the deterministic package digest.
	// (Do not hash the binary/README entries, which are deliberately mutable.)
	// Recalculate using the exact original canonical format.
	h.Reset()
	for i, k := range keys {
		v := m.Files[k]
		if i > 0 {
			fmt.Fprint(h, "\n")
		}
		fmt.Fprintf(h, "%s\t%d\t%s", k, v.Bytes, v.SHA256)
	}
	if hex.EncodeToString(h.Sum(nil)) != expectedRuntimeManifestSHA {
		return fmt.Errorf("runtime manifest does not match pinned R58 build")
	}
	for _, k := range keys {
		rel := strings.TrimPrefix(k, "ramadan-war/")
		// Reject odd/unsafe manifest paths before joining, even though digest is pinned.
		if rel == "" || rel == "." || strings.Contains(rel, "\\") || filepath.IsAbs(rel) || strings.HasPrefix(rel, "../") || strings.Contains(rel, "/../") {
			return fmt.Errorf("invalid game path %q", k)
		}
		path := filepath.Join(packageRoot, filepath.FromSlash(k))
		st, err := os.Lstat(path)
		if err != nil {
			return fmt.Errorf("missing game file %s: %w", k, err)
		}
		if !st.Mode().IsRegular() {
			return fmt.Errorf("game file is not regular: %s", k)
		}
		v := m.Files[k]
		if st.Size() != v.Bytes {
			return fmt.Errorf("game file size mismatch: %s", k)
		}
		f, err := os.Open(path)
		if err != nil {
			return fmt.Errorf("open game file %s: %w", k, err)
		}
		sh := sha256.New()
		_, copyErr := io.Copy(sh, f)
		closeErr := f.Close()
		if copyErr != nil {
			return fmt.Errorf("read game file %s: %w", k, copyErr)
		}
		if closeErr != nil {
			return fmt.Errorf("close game file %s: %w", k, closeErr)
		}
		if hex.EncodeToString(sh.Sum(nil)) != v.SHA256 {
			return fmt.Errorf("game file SHA-256 mismatch: %s", k)
		}
	}
	fmt.Printf("R58 runtime integrity PASS: %d/%d files (SHA-256)\n", len(keys), expectedRuntimeFileCount)
	return nil
}

func main() {
	lan := flag.Bool("lan", false, "Opt-in: allow devices on your trusted local network to connect")
	noOpen := flag.Bool("no-open", false, "Do not open a browser automatically")
	verifyOnly := flag.Bool("verify-only", false, "Verify the game files and exit without starting a server")
	flag.Parse()
	exe, err := os.Executable()
	if err != nil {
		log.Fatal(err)
	}
	packageRoot := filepath.Dir(exe)
	if err := verifyRuntime(packageRoot); err != nil {
		log.Fatalf("Game integrity check FAILED; no server started: %v", err)
	}
	if *verifyOnly {
		return
	}
	root := filepath.Join(packageRoot, "ramadan-war")
	host := "127.0.0.1"
	if *lan {
		host = "0.0.0.0"
	}
	ln, err := net.Listen("tcp", net.JoinHostPort(host, "0"))
	if err != nil {
		log.Fatal(err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	mux := http.NewServeMux()
	files := http.FileServer(http.Dir(root))
	mux.Handle("/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Referrer-Policy", "no-referrer")
		files.ServeHTTP(w, r)
	}))
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second}
	url := fmt.Sprintf("http://127.0.0.1:%d/", port)
	fmt.Println("Ramadan War R58 — private offline game")
	fmt.Println("Open:", url)
	if *lan {
		fmt.Println("LAN mode enabled: use your computer's LAN IP and port", port, "only on a trusted network. Do not port-forward.")
	}
	fmt.Println("No accounts, MOJ1 or online payment. Close this window to stop the local server.")
	if !*noOpen {
		var cmd *exec.Cmd
		switch runtime.GOOS {
		case "windows":
			cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
		case "darwin":
			cmd = exec.Command("open", url)
		default:
			cmd = exec.Command("xdg-open", url)
		}
		if err := cmd.Start(); err != nil && !strings.Contains(err.Error(), "executable file not found") {
			fmt.Println("Open the URL manually:", err)
		}
	}
	log.Fatal(srv.Serve(ln))
}
