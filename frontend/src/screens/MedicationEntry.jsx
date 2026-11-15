import { useRef, useState } from "react";
import { api } from "../api/index.js";
import { Layout } from "../components/Layout.jsx";
import { Button, Notice, PageTitle, Spinner, TextField } from "../components/ui.jsx";
import { useErrorMessage } from "../context.jsx";
import { checkImageFile } from "../lib/imageCheck.js";
import { LIMITS } from "../lib/limits.js";
import { plural } from "../lib/format.js";
import { useLoad } from "../lib/useLoad.js";
import { navigate, paths } from "../router.js";

export function MedicationEntry({ listId }) {
  const toMessage = useErrorMessage();
  const { data: list, loading, error, setData } = useLoad(() => api.getList(listId), listId);
  const [text, setText] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // { id, value }
  const input = useRef(null);
  const fileInput = useRef(null);
  const cameraInput = useRef(null);

  if (loading) return <Layout><Spinner label="Loading your list" /></Layout>;
  if (error) return <Layout><Notice tone="error" title="We could not open this list">{error}</Notice></Layout>;

  const items = list.items;
  const remaining = LIMITS.MAX_MEDS_PER_LIST - items.length;

  async function add(e) {
    e.preventDefault();
    const names = text.split(/[,\n;]+/).map((s) => s.trim()).filter(Boolean);
    if (!names.length) { setFieldError("Enter a medicine name."); input.current?.focus(); return; }
    setFieldError(""); setBusy(true);
    try {
      setData(await api.addNames(listId, names));
      setText(""); setStatus(`Added ${plural(names.length, "medicine")}.`);
      input.current?.focus();
    } catch (err) {
      setFieldError(toMessage(err));
    } finally { setBusy(false); }
  }

  async function upload(file) {
    setUploadError(""); setStatus("");
    if (!file) return;
    setBusy(true);
    try {
      const problem = await checkImageFile(file);
      if (problem) { setUploadError(problem); return; }
      const res = await api.uploadImage(listId, file);
      setData(res.list);
      setStatus(res.added
        ? `Read ${plural(res.added, "medicine name")} from your photo. Check them on the next step.`
        : "We could not find a medicine name in that photo. Type the names instead, or try a clearer photo.");
    } catch (err) {
      setUploadError(toMessage(err));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
      if (cameraInput.current) cameraInput.current.value = "";
    }
  }

  async function saveEdit() {
    try {
      setData(await api.editItem(listId, editing.id, editing.value));
      setEditing(null); setFieldError("");
    } catch (err) { setFieldError(toMessage(err)); }
  }

  async function remove(id) {
    try { setData(await api.removeItem(listId, id)); setStatus("Removed."); }
    catch (err) { setFieldError(toMessage(err)); }
  }

  return (
    <Layout step="medicines" listId={listId}>
      <PageTitle sub="Type each medicine name, or upload a photo of a printed label or prescription. You will check the names on the next step.">
        Add your medicines
      </PageTitle>

      <form onSubmit={add} className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end">
        <TextField
          className="flex-1" label="Medicine name" inputRef={input}
          value={text} onChange={(e) => setText(e.target.value)} error={fieldError}
          hint="Type one name, or several separated by commas. Brand names work too."
          autoComplete="off" maxLength={LIMITS.NAME_MAX * 5}
        />
        <Button type="submit" disabled={busy || remaining <= 0} className="sm:mb-[1.65rem]">Add</Button>
      </form>

      <section aria-labelledby="upload-h" className="mt-8 border-t border-line pt-6">
        <h2 id="upload-h" className="text-xl font-bold">Upload label or prescription</h2>
        <p className="mt-1 max-w-prose text-ink-soft">
          Use a clear photo of printed text, JPEG or PNG, up to {LIMITS.MAX_IMAGE_MB} MB. Handwriting is not supported.
          You have used {list.images.length} of {LIMITS.MAX_IMAGES_PER_LIST} photos.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          <input ref={fileInput} id="file" type="file" accept="image/jpeg,image/png" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} />
          <Button variant="secondary" disabled={busy || list.images.length >= LIMITS.MAX_IMAGES_PER_LIST} onClick={() => fileInput.current?.click()}>Choose a photo</Button>
          <input ref={cameraInput} id="camera" type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} />
          <Button variant="secondary" disabled={busy || list.images.length >= LIMITS.MAX_IMAGES_PER_LIST} onClick={() => cameraInput.current?.click()}>Take a photo</Button>
        </div>
        {uploadError && <Notice tone="error" title="We could not use that photo" className="mt-3">{uploadError} You can choose another file or type the names instead.</Notice>}
      </section>

      <div role="status" aria-live="polite" className="min-h-6 py-2 font-semibold text-brand-dark">{status}</div>

      <section aria-labelledby="list-h" className="mt-2">
        <div className="flex items-baseline justify-between border-b-2 border-ink pb-1">
          <h2 id="list-h" className="text-xl font-bold">Your list</h2>
          <p className="text-ink-soft">{items.length} of {LIMITS.MAX_MEDS_PER_LIST}</p>
        </div>
        {items.length === 0 ? (
          <p className="py-6 text-ink-soft">No medicines yet. Type a name above or upload a photo of a label.</p>
        ) : (
          <ul>
            {items.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-line py-2">
                {editing?.id === item.id ? (
                  <form className="flex flex-1 flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); saveEdit(); }}>
                    <TextField className="min-w-48 flex-1" label="Edit medicine name" value={editing.value} onChange={(e) => setEditing({ ...editing, value: e.target.value })} />
                    <Button type="submit">Save</Button>
                    <Button variant="quiet" onClick={() => setEditing(null)}>Cancel</Button>
                  </form>
                ) : (
                  <>
                    <p className="min-w-0 flex-1">
                      <span className="font-semibold">{item.raw}</span>
                      <span className="ml-2 text-sm text-ink-soft">{item.source === "ocr" ? "From photo" : "Typed"}</span>
                    </p>
                    <span className="flex gap-1">
                      <Button variant="quiet" onClick={() => setEditing({ id: item.id, value: item.raw })} aria-label={`Edit ${item.raw}`}>Edit</Button>
                      <Button variant="danger" onClick={() => remove(item.id)} aria-label={`Remove ${item.raw}`}>Remove</Button>
                    </span>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-8 flex flex-wrap justify-end gap-3">
        <Button disabled={items.length === 0} onClick={() => navigate(paths.confirm(listId))}>Next: check names</Button>
      </div>
      {items.length === 0 && <p className="mt-2 text-right text-sm text-ink-soft">Add at least one medicine to continue.</p>}
    </Layout>
  );
}
