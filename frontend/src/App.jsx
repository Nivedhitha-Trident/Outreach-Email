
import { useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  Sparkles,
  Loader2,
  CheckCircle2,
  Building2,
  Mail,
  Briefcase,
  Send,
  Moon,
  Sun,
} from "lucide-react";

import { request, upload } from "./api";
import "./styles.css";

function App() {
  const [theme, setTheme] = useState(
    localStorage.getItem("theme") || "dark"
  );

  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState("");

  const [dashboard, setDashboard] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [previewLead, setPreviewLead] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoadingLeadId, setPreviewLoadingLeadId] = useState(null);
  const [leadSendStatuses, setLeadSendStatuses] = useState({});

  const [message, setMessage] = useState(null);
  const [sendLoading, setSendLoading] = useState(false);

  const fileRef = useRef(null);

  const leads = dashboard?.leads || [];

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
  }

  async function handleUpload(file) {
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setUploading(true);
    setUploaded(false);
    setMessage(null);

    try {
      const data = await upload("/api/leads/upload", form);

      const dashboardData = await request("/api/dashboard");

      setDashboard(dashboardData);
      setUploadedFileName(file.name);
      setLeadSendStatuses({});

      if (dashboardData?.leads?.length) {
        const firstLead = dashboardData.leads[0];

        const leadData = await request(
          `/api/leads/${firstLead.id}`
        );

        setSelectedLead(leadData);
      }

      setUploaded(true);

      setMessage({
        type: "success",
        text: `File uploaded: ${file.name} (${dashboardData.leads.length} leads imported)`,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setUploading(false);
    }
  }

  async function selectLead(lead) {
    const data = await request(`/api/leads/${lead.id}`);

    setSelectedLead(data);
    return data;
  }

  async function openLeadPreview(lead) {
    setPreviewLoadingLeadId(lead.id);

    try {
      let data = await request(`/api/leads/${lead.id}`);

      if (!data?.email?.content && !data?.email?.body) {
        data = await request(`/api/leads/${lead.id}/generate-email`, {
          method: "POST",
        });
      }

      setPreviewLead(data);
      setPreviewOpen(true);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setPreviewLoadingLeadId(null);
    }
  }

  async function sendEmail() {
    if (!leads.length) return;

    setSendLoading(true);
    setLeadSendStatuses({});

    try {
      let sentCount = 0;
      const failedLeads = [];

      for (const lead of leads) {
        setLeadSendStatuses((current) => ({
          ...current,
          [lead.id]: "Generating",
        }));

        const leadDetail = await request(`/api/leads/${lead.id}`);
        let emailContent =
          leadDetail?.email?.content ||
          leadDetail?.email?.body ||
          leadDetail?.generated?.content ||
          "";

        if (!emailContent) {
          const generated = await request(
            `/api/leads/${lead.id}/generate-email`,
            {
              method: "POST",
            }
          );
          emailContent =
            generated?.email?.content ||
            generated?.email?.body ||
            generated?.generated?.content ||
            "";
          setLeadSendStatuses((current) => ({
            ...current,
            [lead.id]: "Generated",
          }));
        } else {
          setLeadSendStatuses((current) => ({
            ...current,
            [lead.id]: "Generated",
          }));
        }

        if (!emailContent) {
          setLeadSendStatuses((current) => ({
            ...current,
            [lead.id]: "Failed",
          }));
          failedLeads.push(lead.company || lead.name || lead.id);
          continue;
        }

        setLeadSendStatuses((current) => ({
          ...current,
          [lead.id]: "Sending",
        }));

        await request(`/api/leads/${lead.id}/send-email`, {
          method: "POST",
          body: JSON.stringify({
            content: emailContent,
          }),
        });

        setLeadSendStatuses((current) => ({
          ...current,
          [lead.id]: "Sent",
        }));

        sentCount += 1;
      }

      setMessage({
        type: "success",
        text:
          failedLeads.length > 0
            ? `Sent ${sentCount} emails. Skipped ${failedLeads.length} leads with no email draft.`
            : `Sent ${sentCount} emails successfully.`,
      });

      const dashboardData = await request("/api/dashboard");
      setDashboard(dashboardData);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setSendLoading(false);
    }
  }

  return (
    <div className="app">
      {/* Background Orbs */}
      <div className="orb orb1" />
      <div className="orb orb2" />
      <div className="orb orb3" />

      {/* Theme Toggle */}
      <button className="theme-toggle" onClick={toggleTheme}>
        {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
      </button>

      <div className="container">
        {/* HEADER */}
        <section className="hero glass">
          <div className="hero-content">
            <h1>
            <span>LeadReach AI</span> <br/>
            </h1>

            <div className="hero-flow" aria-label="Workflow diagram">
              <div className="hero-flow-node upload">
                <FileSpreadsheet size={18} />
              </div>
              <div className="hero-flow-arrow" />
              <div className="hero-flow-node ai">
                <Sparkles size={18} />
              </div>
              <div className="hero-flow-arrow" />
              <div className="hero-flow-node cards">
                <Building2 size={18} />
              </div>
              <div className="hero-flow-arrow" />
              <div className="hero-flow-node send">
                <Send size={18} />
              </div>
            </div>

            <div className="hero-flow-labels">
              <p>Upload</p>
              <p>Analyse</p>
              <p>Generate</p>
              <p>Send</p>
            </div>

            <h2><span>Generate AI Emails</span></h2>
          </div>

          <div className="hero-upload">
            <div className="upload-card glass">
              <div className="upload-main">
                <div className="upload-icon">
                  <UploadCloud size={44} />
                </div>

                <h2>{uploaded ? "Replace file" : "Upload leads"}</h2>

                {uploaded && uploadedFileName && (
                  <div className="upload-status">
                    <span className="upload-status-label">File uploaded</span>
                    <strong>{uploadedFileName}</strong>
                  </div>
                )}

                <button
                  className="upload-btn"
                  onClick={() => fileRef.current?.click()}
                >
                  <FileSpreadsheet size={18} />
                  {uploaded ? "Upload another file" : "Choose Excel File"}
                </button>

                <input
                  ref={fileRef}
                  type="file"
                  hidden
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) =>
                    handleUpload(e.target.files?.[0])
                  }
                />

                <div className="supported">
                  {uploaded ? "Upload a new file to replace the current one" : "CSV, XLSX & XLS"}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* MODERN FULLSCREEN LOADER */}
        {uploading && (
          <section className="loader-screen">
            <div className="loader-card glass">
              <div className="ai-loader">
                <div />
                <div />
                <div />
              </div>

              <h2>Analyzing Excel File</h2>

              <p>
                AI is processing leads and generating outreach
                pipeline...
              </p>

              <div className="loading-steps">
                {/* <div className="step active">
                  Reading spreadsheet
                </div>

                <div className="step active">
                  Extracting lead data
                </div> */}

                <div className="step pulse">
                  Building AI lead cards
                </div>
              </div>
            </div>
          </section>
        )}

        {/* SUCCESS MESSAGE */}
        {message && (
          <div className={`message ${message.type}`}>
            <span>{message.text}</span>

            <button onClick={() => setMessage(null)}>
              ✕
            </button>
          </div>
        )}

        {/* SHOW LEAD CARDS ONLY AFTER UPLOAD */}
        {uploaded && !uploading && (
          <>
            <div className="section-header pipeline-header">
              <div>
                <h2>Lead Pipeline</h2>

                <p>{leads.length} Leads Available</p>
              </div>

              <section className="send-bar compact">
                <button
                  className="send-btn"
                  disabled={!leads.length || sendLoading}
                  onClick={sendEmail}
                >
                  {sendLoading ? (
                    <>
                      <Loader2 className="spin" size={18} />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      Send All Emails
                    </>
                  )}
                </button>
              </section>
            </div>

            <div className="lead-grid">
              {leads.map((lead) => {
                const sendStatus = leadSendStatuses[lead.id];
                const statusText = sendStatus || (lead.sent ? "Sent" : "Ready");
                const statusClass =
                  sendStatus === "Sent" || lead.sent
                    ? "green"
                    : sendStatus === "Failed"
                      ? "red"
                      : sendStatus
                        ? "yellow"
                        : "yellow";

                return (
                <div
                  key={lead.id}
                  className={`lead-card glass ${
                    selectedLead?.lead?.id === lead.id
                      ? "active"
                      : ""
                  }`}
                  onClick={() => selectLead(lead)}
                >
                  <div className="lead-top">
                    <div className="company-icon">
                      <Building2 size={18} />
                    </div>

                    {lead.sent ? (
                      <CheckCircle2
                        size={20}
                        className="sent-icon"
                      />
                    ) : (
                      <div className="pulse-dot" />
                    )}
                  </div>

                  <h3>{lead.company}</h3>

                  <div className="lead-name">
                    {lead.name}
                  </div>

                  <div className="lead-info">
                    <div>
                      <Briefcase size={15} />
                      {lead.designation || "Professional"}
                    </div>

                    <div>
                      <Mail size={15} />
                      {lead.email}
                    </div>
                  </div>

                  <div className="lead-footer">
                    <span className={`status ${statusClass}`}>
                      {statusText}
                    </span>

                    <span className="industry">
                      {lead.industry || "Technology"}
                    </span>
                  </div>

                  <button
                    type="button"
                    className="view-btn"
                    disabled={previewLoadingLeadId === lead.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      openLeadPreview(lead);
                    }}
                  >
                    {previewLoadingLeadId === lead.id ? "Loading..." : "View"}
                  </button>
                </div>
                );
              })}
            </div>
          </>
        )}

        {previewOpen && previewLead && (
          <div
            className="mail-modal-backdrop"
            onClick={() => setPreviewOpen(false)}
          >
            <div
              className="mail-modal glass"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="mail-modal-header">
                <div>
                  <div className="send-label">Generated Mail</div>
                  <h3>
                    {previewLead.lead?.company ||
                      previewLead.lead?.name ||
                      "Lead"}
                  </h3>
                </div>

                <button
                  type="button"
                  className="mail-modal-close"
                  onClick={() => setPreviewOpen(false)}
                >
                  ✕
                </button>
              </div>

              <div className="mail-preview">
                {previewLead.email?.content ||
                previewLead.email?.body ||
                previewLead.generated?.content ? (
                  <pre>
                    {previewLead.email?.content ||
                      previewLead.email?.body ||
                      previewLead.generated?.content}
                  </pre>
                ) : (
                  <p>No generated email content is available for this lead.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
