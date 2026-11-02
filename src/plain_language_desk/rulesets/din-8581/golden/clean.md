# So prüfen Sie den Einsatz

Der Einsatzcheck bestätigt, dass die Veröffentlichung im Cluster angekommen
ist. Führen Sie den Check aus, bevor Sie die Veröffentlichung ankündigen.

Der Check vergleicht 2 Image-Digests: den gespeicherten Digest und den
Digest im Cluster. Bei unterschiedlichen Werten ist der Rollout nicht
abgeschlossen. Warten Sie 5 Minuten und führen Sie den Check erneut aus.

Bei 3 fehlgeschlagenen Versuchen: Öffnen Sie einen Incident und stoppen Sie
die Ankündigung.
