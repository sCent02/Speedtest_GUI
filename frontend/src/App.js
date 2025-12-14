import { useState } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Download, CheckCircle2, AlertCircle, TrendingUp } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [urls, setUrls] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [processingCount, setProcessingCount] = useState(0);

  const sampleUrls = `https://www.speedtest.net/my-result/a/11295159508
https://www.speedtest.net/my-result/a/11295160960
https://www.speedtest.net/my-result/a/11295162242
https://www.speedtest.net/my-result/a/11295175102
https://www.speedtest.net/my-result/a/11295176782`;

  const handleLoadSample = () => {
    setUrls(sampleUrls);
    setResult(null);
    setErrors([]);
  };

  const handleProcess = async () => {
    if (!urls.trim()) {
      setErrors(["Please enter at least one URL"]);
      return;
    }

    setLoading(true);
    setResult(null);
    setErrors([]);

    try {
      const urlList = urls.split("\n").filter(url => url.trim());
      setProcessingCount(urlList.length);
      
      // Set longer timeout for screenshot processing (5 minutes)
      const response = await axios.post(`${API}/process-speedtest`, {
        urls: urlList
      }, {
        timeout: 300000  // 5 minutes timeout
      });

      setResult(response.data);
      
      // Auto-download the file
      if (response.data.file_path) {
        const fileName = response.data.file_path.split("/").pop();
        const downloadUrl = `${API}/download/${fileName}`;
        
        // Create temporary link and trigger download
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }

      if (response.data.errors && response.data.errors.length > 0) {
        setErrors(response.data.errors);
      }
    } catch (error) {
      console.error("Error processing speedtest:", error);
      if (error.code === 'ECONNABORTED') {
        setErrors(["Request timed out. Please try with fewer URLs or check if the URLs are valid and accessible."]);
      } else {
        setErrors([
          error.response?.data?.detail || "Failed to process speedtest URLs. Please try again."
        ]);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-4">
            <TrendingUp className="w-12 h-12 text-blue-600" />
          </div>
          <h1 className="text-5xl font-bold text-gray-900 mb-3" style={{ fontFamily: 'Inter, sans-serif' }}>
            Speedtest Screenshot Tool
          </h1>
          <p className="text-lg text-gray-600" style={{ fontFamily: 'Inter, sans-serif' }}>
            Convert your speedtest.net results into a professional Excel report
          </p>
        </div>

        {/* Main Card */}
        <Card className="shadow-xl border-0 bg-white/80 backdrop-blur-sm" data-testid="main-card">
          <CardHeader>
            <CardTitle className="text-2xl" style={{ fontFamily: 'Inter, sans-serif' }}>Enter Speedtest URLs</CardTitle>
            <CardDescription style={{ fontFamily: 'Inter, sans-serif' }}>
              Paste your speedtest.net result URLs below (one per line)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              data-testid="url-input"
              placeholder="https://www.speedtest.net/my-result/a/11295159508&#10;https://www.speedtest.net/my-result/a/11295160960&#10;..."
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
              rows={8}
              className="font-mono text-sm"
              style={{ fontFamily: 'Fira Sans, monospace' }}
            />

            <div className="flex gap-3">
              <Button
                data-testid="load-sample-btn"
                onClick={handleLoadSample}
                variant="outline"
                className="flex-1"
                disabled={loading}
              >
                Load Sample URLs
              </Button>
              <Button
                data-testid="process-btn"
                onClick={handleProcess}
                disabled={loading || !urls.trim()}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing {processingCount} URL{processingCount !== 1 ? 's' : ''}...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Generate Excel
                  </>
                )}
              </Button>
            </div>

            {/* Success Message */}
            {result && result.success && (
              <Alert className="bg-green-50 border-green-200" data-testid="success-alert">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {result.message} - Excel file downloaded successfully!
                </AlertDescription>
              </Alert>
            )}

            {/* Error Messages */}
            {errors.length > 0 && (
              <Alert className="bg-amber-50 border-amber-200" data-testid="error-alert">
                <AlertCircle className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-800" style={{ fontFamily: 'Inter, sans-serif' }}>
                  <div className="font-semibold mb-1">Some issues occurred:</div>
                  <ul className="list-disc list-inside space-y-1">
                    {errors.map((error, idx) => (
                      <li key={idx} className="text-sm">{error}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Info Section */}
        <div className="mt-8 p-6 bg-white/60 backdrop-blur-sm rounded-lg border border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-2" style={{ fontFamily: 'Inter, sans-serif' }}>How it works:</h3>
          <ol className="list-decimal list-inside space-y-2 text-gray-700 text-sm" style={{ fontFamily: 'Inter, sans-serif' }}>
            <li>Paste your speedtest.net result URLs (one per line)</li>
            <li>Click "Generate Excel" to process</li>
            <li>Screenshots are captured and organized in Excel (5 per row)</li>
            <li>Download starts automatically when ready</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

export default App;
