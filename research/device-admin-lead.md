# Epson Device Admin: historical protocol lead

This records an earlier protocol lead for context. The user has excluded Epson's official admin and updater tools from the installation plan. Our current work uses an independently built client and offline emulation of the firmware's own network path. Device Admin is not a verified ET-3850 custom-firmware installation path.

- Epson's [Device Admin User's Guide](https://files.support.epson.com/docid/other/npd6822_00_en.pdf), pages 70–75, describes a firmware update schedule with **Load from PC**, which uses a firmware file selected by the operator. It says updates can be performed only for devices supporting that feature.
- Epson's [ET-3850 series user guide](https://download4.epson.biz/sec_pubs/et-3850_series/useg/en/manual.pdf) says the administrator password can be changed through Epson Device Admin. An [Epson product brochure](https://epsonemear.a.bigcontent.io/v1/static/a15659-brochure-lores-fr-fr-solutions_for_wf_and_et_series) lists ET-3850 with Epson Device Admin. Those establish management compatibility, but not that this model exposes Device Admin's local-file firmware update feature.
- Epson's [Device Admin port FAQ](https://epson.com/faq/SPT_DEVICEADMIN-NS~faq-290010?faq_cat=faq-topFaqs) lists TCP 443 for HTTPS communication and firmware updates. The ET-3850 does listen on 443, though a matching active upload route and Device Admin handshake have not been captured.
- Epson's [ET-3850 recovery package page](https://epson.com/Support/Printers/All-In-Ones/ET-Series/Epson-ET-3850/s/SPT_C11CJ61201) labels that recovery updater USB-only. Its RCX/EFU content may or may not be accepted by Device Admin's Load from PC workflow.

The older and current official RCX signatures both verify against the same embedded public key. An offline one-byte change in the current RCX payload causes [`verify_rcx_signature.py`](../scripts/verify_rcx_signature.py) to reject it. This confirms the signature covers the payload bytes, while leaving open whether the ET-3850 checks that signature, how it roots trust, and whether Device Admin applies its own checks.

The historical lead did not establish a protocol or install capability. The independent path now being investigated is the printer's `/DOWN/` request relay and its controller-side approval and signature checks. See [generic stream trace](generic-down-stream.md) and [controller CROM trace](controller-crom-trace.md).

No firmware was sent to the live printer while investigating this lead.
