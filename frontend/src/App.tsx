import { CssBaseline, ThemeProvider } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { api } from './api/client';
import PlannerPage from './components/PlannerPage';
import { SelectionProvider } from './hooks/SelectionProvider';
import { theme } from './theme';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

export default function App() {
  // Wake a sleeping API instance while the user fills in the form (harmless if it is awake).
  useEffect(() => {
    void api.warmUp();
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <QueryClientProvider client={queryClient}>
          <SelectionProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<PlannerPage />} />
                <Route path="/plans/:planId" element={<PlannerPage />} />
              </Routes>
            </BrowserRouter>
          </SelectionProvider>
        </QueryClientProvider>
      </LocalizationProvider>
    </ThemeProvider>
  );
}
