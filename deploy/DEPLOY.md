# Deploying Fugee — Hugging Face Space + Modal

The demo runs in two pieces: the **Gradio UI on a free HF CPU Space**, calling the
**LLM + embeddings on a GPU Ollama endpoint on Modal**. Same code, same model
(`lfm2.5:8b`), just on rented GPU.

```
HF Space (free CPU)  ──HTTPS, proxy-auth──▶  Modal (L4 GPU, ollama serve)
app/app.py                                    lfm2.5:8b + nomic-embed-text
```

Run the steps in order. Steps that only the maintainer can do (auth, secrets) are
marked **[you]**.

---

## 0. Prerequisites (already done in this repo)

- `deploy/modal_app.py` is deployed and **kept warm**
  (`MODAL_MIN_CONTAINERS=1`) → endpoint `https://hf-labs--fugee-ollama-serve.modal.run`.
- A Modal **Proxy Auth Token** exists; its id/secret are in `.env.modal`
  (gitignored) as `MODAL_KEY` / `MODAL_SECRET`.
- Models cached in the Modal Volume (`modal run deploy/modal_app.py::download_models`).

Re-check the endpoint is warm before a demo:

```bash
set -a; . ./.env.modal; set +a
curl -s -o /dev/null -w "%{http_code}\n" \
  https://hf-labs--fugee-ollama-serve.modal.run/api/version \
  -H "Modal-Key: $MODAL_KEY" -H "Modal-Secret: $MODAL_SECRET"     # expect 200
```

---

## 1. **[you]** Authenticate the HF CLI

Create a token with **write** access at <https://huggingface.co/settings/tokens>,
then:

```bash
hf auth login        # paste the write token
```

---

## 2. **[you]** Create the Space in the hackathon org

Web: **New Space** → Owner `build-small-hackathon`, name `fugee`, SDK **Gradio**,
hardware **CPU basic (free)**, **Public**. Or CLI:

```bash
hf repo create build-small-hackathon/fugee --repo-type space --space-sdk gradio
```

(If the flag name differs on your CLI version, run `hf repo create --help`.)

---

## 3. Push the code to the Space

The Space is its own git repo. Add it as a remote and push `main` (force, to
replace the starter README HF created on the first deploy):

```bash
git remote add space https://huggingface.co/spaces/build-small-hackathon/fugee
git push space main --force
```

This pushes everything except gitignored files — code, `countries.json`,
`countries_enriched.json`, bundled fonts, etc. It does **not** include the binary
data the HF Hub requires Xet/LFS for — the 23 MB RAG index and the source PDFs —
which are uploaded next. The Space starts building on push.

---

## 4. Upload the binary data (RAG index + source PDFs)

These are gitignored (the HF Hub rejects binaries in plain git), so they're
uploaded with `huggingface_hub`, which stores them via Xet automatically — **no
local git-lfs needed**.

⚠️ **Gotcha:** the hub upload helpers honour the *repo's* `.gitignore` (which we
just pushed, and it ignores these very files) — they will silently skip them. So
first delete `.gitignore` from the Space (a deployment doesn't need it), then
upload. This Python snippet does the whole thing:

```bash
python - <<'PY'
from huggingface_hub import HfApi
api, repo = HfApi(), "build-small-hackathon/fugee"
api.delete_file(".gitignore", repo_id=repo, repo_type="space",
                commit_message="Drop .gitignore on the Space so data assets upload")
api.upload_file(path_or_fileobj="specs/data/guidelines_index.json",
                path_in_repo="specs/data/guidelines_index.json",
                repo_id=repo, repo_type="space")
api.upload_folder(folder_path="specs/data/guidelines",
                  path_in_repo="specs/data/guidelines",
                  repo_id=repo, repo_type="space", allow_patterns=["*.pdf"])
print("done")
PY
```

> ⚠️ **Don't `git push --force` after this.** The index/PDFs live *only* on the
> Space (uploaded above), not in git. A force-push resets `main` to your local
> commit and would **delete** them. To change code later: `git fetch space &&
> git rebase space/main` then push, or edit on the Space, or re-run this upload
> after the force-push.

---

## 5. **[you]** Set the Space secrets & variables

Space → **Settings → Variables and secrets**. The app reads these from the
environment (its `.env` loader never overrides real env vars).

**Secrets** (encrypted):

| Name | Value |
|------|-------|
| `OLLAMA_HOST` | `https://hf-labs--fugee-ollama-serve.modal.run` |
| `MODAL_KEY` | your Modal Proxy Auth Token id (`wk-…`) |
| `MODAL_SECRET` | your Modal Proxy Auth Token secret (`ws-…`) |

**Variables** (public):

| Name | Value |
|------|-------|
| `MODEL_ID` | `lfm2.5:8b` |
| `MODEL_PROVIDER` | `ollama` |
| `NUM_CTX` | `16384` |

> `MODEL_ID` **must** be set — the code default is `qwen2.5:7b`, which isn't on
> the Modal endpoint. `OLLAMA_HOST` + `MODAL_KEY` + `MODAL_SECRET` are required for
> the Space to reach the model. The Modal **account** token never goes here — it
> stays in `~/.modal.toml` on your machine.

Setting a secret restarts the Space.

---

## 6. Verify the live Space

Open `https://huggingface.co/spaces/build-small-hackathon/fugee`, wait for the
build (watch the **Logs** tab), then walk a full flow: language → interview →
assessment → recommendations → documents. First model call may take a few seconds
even though Modal is warm.

If PDF generation errors in the logs, it's a missing system lib — confirm
`packages.txt` installed (Pango/HarfBuzz/Noto fonts).

---

## 7. Submit & costs

- **Submission:** on the hackathon *submit* page, enter `fugee` under
  `build-small-hackathon/` → it loads the README and writes track/badge tags into
  the frontmatter → commit that back (`git pull space main` then push, or edit on HF).
- **GPU limit:** the "10 ZeroGPU apps per user" rule does **not** apply — we use
  Modal, not ZeroGPU.
- **After the demo window**, stop the Modal meter:

  ```bash
  MODAL_MIN_CONTAINERS=0 modal deploy deploy/modal_app.py   # scale to zero
  # or fully stop:
  modal app stop fugee-ollama
  ```

  Scale-to-zero keeps the deployment but costs nothing while idle (cold start
  ~40 s on the next request).
