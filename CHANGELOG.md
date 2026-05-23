# Changelog

## v3.8.4 (2026-05-23)

### Bug fixes


- Defer loop-coupled state in apiconnectionmanager to start() ([`dbb3bf1`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/dbb3bf11f4d48302e6880fb90caca0faf87e7a20))


### Refactoring


- Extract spurious-cancellation predicate to shared helper ([`af0c4b0`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/af0c4b0b947de5e6f1f2654822170da549292440))


## v3.8.3 (2026-05-23)

### Bug fixes


- Harden esphomeclient.__del__ against shutdown and leaks (#333) ([`fa24a97`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/fa24a9792673d8bcd58760f15036059f49598eb3))


## v3.8.2 (2026-05-23)

### Documentation


- Document on-demand active scan window (feature_state_and_mode) ([`916ad6b`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/916ad6bcb03e9715a39d958828375f9a0ffcc1f5))


- Add autodoc api reference for public package surface ([`f09d779`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f09d779ebd015ebced3e8b56fcfa5b880ed0039c))


### Bug fixes


- Preserve method metadata in api_error_as_bleak_error decorator ([`3d1a0fd`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/3d1a0fdc912e50c96496f24a88bbd53df0e49592))


## v3.8.1 (2026-05-23)

### Bug fixes


- Parallelize cython build_ext and clean up redundant pass ([`61f2b14`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/61f2b14f6d6c56926238bd3c645152bbff4208e1))


## v3.8.0 (2026-05-23)

### Features


- Implement on-demand active scan window via proxy mode set ([`8b6725f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/8b6725feec1ebbf10eebe884efc94f319f609334))


### Documentation


- Correct stale connect() docstring (returns + find_device_by_address) ([`1fc998f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1fc998f2780f4cc1e347b1f7cfbf315cc507c466))


- Correct misleading docstrings on pair/cache/conn-params ([`ee69d1a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/ee69d1aef1dc0e2c5b7c19d2c97f28a082488a3d))


- Clarify _get_services and stop_notify behavior ([`98ad872`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/98ad872347d8bbd4cb62b5dda8d346227316e4a6))


- Correct stale comment and thin docstrings on device/conn-mgr ([`8d5f221`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/8d5f221c0a6d46eba4a3bbeac0b033f56bcad309))


- Document that callbacks are ignored in connect_scanner because they auto teardown on connect ([`e0a8e41`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/e0a8e4128e748424b90445602ffa01180c25f7d1))


## v3.7.6 (2026-05-21)

### Performance improvements


- Hoist max_write_without_response callable above char loop (#334) ([`8df6144`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/8df614450aae77bb47c0b003c1c6096d7481bcd5))


### Bug fixes


- Return mac strings from scanner.get_allocations (#330) ([`174371d`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/174371d68da24ae93082c41e7688282f49232b1d))


### Testing


- Cover __del__ leaked-subscription warning ([`cfdb8e9`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/cfdb8e9364183e18e52ad6c98deb128ff1181ef9))


- Cover cached-mtu skip in connection-state callback ([`86d9ed3`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/86d9ed3d2cc90fba1d7ad13e84fed905df47536d))


- Cover connect cancel edge branches ([`cd46643`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/cd466437466b50a0b933da1d7989831b4622582f))


- Assert public bleak_esphome package surface ([`f3a1785`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f3a1785d02d3756ac6502b35eeaaef73aad35135))


- Dry up backend tests with shared fixtures and helpers ([`1d01b6e`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1d01b6e6d03afe03418f4eccd7caeb653b9350cd))


- Cover client decorator, error, and notify branches ([`b149beb`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/b149bebd82b3f27522333e8a3207f72467f71cab))


- Cover scanner decoded path, _can_connect, and connect_scanner branches ([`de5b072`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/de5b0726ce49e8a5a29f1469bf45ccb1fef97e1d))


### Documentation


- List all gated feature flags in architecture overview ([`3048d03`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/3048d03c2c9f3a0b6859738e17099051e2ce166e))


- Document low-level connect_scanner workflow ([`2a511fa`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/2a511fa0cc4c0cf809d80973513d7cba631eac23))


- Document esphomestartaborted in usage guide ([`0130633`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/013063364df688f92e36b4202f00895195ae6ceb))


- Add feature flag compatibility matrix to usage guide ([`f1dc52a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f1dc52aebe6cfc23a7364008a6f9eb92499668aa))


- Drop stale backend module references from claude.md ([`650d408`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/650d4085939ed8030729c5755b853b8ffde62a8b))


## v3.7.5 (2026-05-16)

### Bug fixes


- Clear scanner.current_mode when proxy is not running ([`7f25876`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/7f258765d4cbd3ce170a4711401b7705f6a40e42))


- Fire client_data.disconnect_callbacks on esp disconnect ([`a2c90ff`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a2c90ff9406bc8609faf0e7b9d040b2031dc472e))


### Testing


- Silence bledevice deprecation and asyncmock coroutine warnings ([`c2c443d`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c2c443d7fc65356a00fb085f5fcec16af830442d))


- Cover connection_manager on_connect/on_disconnect/stop paths ([`0c680fa`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0c680fa48f74b9062b8da751d9806bf19e5e2be3))


- Add direct coverage for esphomebluetoothcache ([`52f968e`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/52f968e51e248da322d1c793a94f71923a671ea7))


## v3.7.4 (2026-05-14)

### Bug fixes


- Guard wait_for_ble_connections_free against late timer race ([`9ece701`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/9ece701b4bdf190ea33b226541419d0119e9168f))


### Documentation


- Add claude.md with style and tooling guide ([`789088c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/789088c0873ab4f54691f7dfbf913d508ded09cc))


- Explain bluetooth proxy architecture and library scope ([`355cac6`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/355cac657837281220eab7e0701b64713e945054))


## v3.7.3 (2026-04-11)

### Bug fixes


- Shield disconnect cleanup in connect cancel handler ([`a5675c1`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a5675c1b5ec13c25c49b2977c2e177e83654fca0))


## v3.7.2 (2026-04-11)

### Bug fixes


- Convert spurious cancellederror in connect to bleakerror ([`e3cc1c1`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/e3cc1c1f3b2099aba9703578136fa05886326618))


- Convert spurious cancellation in apiconnectionmanager.start to esphomestartaborted ([`9190d8c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/9190d8c5607c2bc099306bc9297cc79ad183a302))


### Documentation


- Add extension methods documentation ([`4d10fca`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4d10fcac05a5d8db9c45825ba631bab7ea207839))


## v3.7.1 (2026-03-07)

### Bug fixes


- Warn when esphome device does not support connection params ([`c07e620`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c07e620f66a12f5fbb8f08e3c384ef561c5a49f0))


## v3.7.0 (2026-03-07)

### Features


- Add ble connection parameters api ([`f40d54f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f40d54f484c1558ce4f75ac025bbb631b15c7793))


## v3.6.1 (2026-03-07)

### Bug fixes


- Update poetry marker for py 3.14 ([`9b7c344`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/9b7c344d1c38d6149278bf55281802578f1b61d0))


## v3.6.0 (2026-01-27)

### Features


- Allow custom gatt read timeouts ([`8ebd2a3`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/8ebd2a397f1e2e21dc7ad1416840ebaafabe2c7b))


## v3.5.0 (2026-01-27)

### Features


- Add support for bleak 2.1.1 ([`0d1e8f6`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0d1e8f67c5f8bc7919163deee7a6f38cad6843b2))


## v3.4.1 (2026-01-25)

### Bug fixes


- Make sure we wait for ccd write in start_notify ([`8ab893f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/8ab893fdc832bc703352186a7aa98005811219dd))


## v3.4.0 (2025-10-04)

### Features


- Add wheels for python 3.14 and bump habluetooth min version ([`cfde020`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/cfde020d60fdc4c20c8b5c50d2b7219818794301))


## v3.3.0 (2025-09-08)

### Features


- Implement get_allocations for esphomescanner for thundering heard problem ([`ecd0454`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/ecd04542b7130fb963ca0f99cf04ba85e496783a))


## v3.2.0 (2025-08-28)

### Features


- Use set_*_mode helpers instead of setting mode directly ([`baa0b4c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/baa0b4c7edda076b9f0e496eafdd328fe2a426fe))


## v3.1.0 (2025-07-03)

### Features


- Add auto pair support for bleak 1.x ([`0d538e8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0d538e8481b0e351b68bd977d431e2b29a38b381))


## v3.0.1 (2025-07-03)

### Bug fixes


- Use characteristic_properties ([`6bba94a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/6bba94aebc789fa7b40c46d41773bd74a054b9b0))


## v3.0.0 (2025-07-03)

### Features


- Add bleak 1.0 support ([`14dd2dd`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/14dd2dd068763680e3c34e3abe8870ecb3f71755))


## v2.16.0 (2025-06-03)

### Features


- Update scanner mode from callback ([`9c093b5`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/9c093b59885e0f3d7c68f8b1b5aa24ab76da4d49))


## v2.15.1 (2025-05-03)

### Bug fixes


- Revert to using python api for scanner ([`0cc7e99`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0cc7e9962f380aa8064608a64c774f074a110fab))


## v2.15.0 (2025-04-29)

### Features


- Bump aioesphomeapi requirement to 30.1.0+ ([`4430f0c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4430f0c716804743247ba7a3b4efe593d6d2952f))


## v2.14.0 (2025-04-27)

### Features


- Switch to using the _async_on_raw_advertisement api ([`eb62775`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/eb6277517fb74955cffabfb162abf3a4815f02e3))


## v2.13.1 (2025-04-03)

### Bug fixes


- Disable 32bit wheels on linux to fix builds ([`4d922b8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4d922b82b073073e710a50da8b1b80be99166d2d))


## v2.13.0 (2025-04-03)

### Features


- Improve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


- Imporve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


- Imporve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


## v2.12.0 (2025-03-13)

### Features


- Only look up _async_on_advertisement once per advertisement group ([`f7a001d`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f7a001d4288d0fec56a7467ebb6759c2658c40dd))


## v2.11.0 (2025-03-05)

### Features


- Reduce size of wheels ([`a52ad36`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a52ad36a8838a8516b7d533f0a5080c50ad9db7e))


## v2.10.2 (2025-03-04)

### Bug fixes


- Wheel builds ([`aa11ec3`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/aa11ec370e58572d79dda34e397013b0006d8ca7))


## v2.10.1 (2025-03-04)

### Bug fixes


- Add missing permissions to upload wheels ([`12b396f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/12b396f8857b89b23ed978202eca37be33b7cf38))


- Add missing permissions to upload wheels ([`12b396f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/12b396f8857b89b23ed978202eca37be33b7cf38))


## v2.10.0 (2025-03-04)

### Features


- Add optional cython for scanner to improve performance ([`a4e0803`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a4e08034f3565fd086432402e68b20feb081a4df))


## v2.9.0 (2025-02-27)

### Features


- Use bluetooth_mac_address for the source if available ([`df7f72c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/df7f72c18234ab95f2fcdc4322bab35d2065294c))


## v2.8.0 (2025-02-27)

### Features


- Simplify examples ([`c67c856`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c67c856207724f7ea81fd2f924a3f9940ddd58d8))


## v2.7.1 (2025-02-04)

### Bug fixes


- Update poetry to v2 ([`f1edae5`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f1edae54bba1320c6f8292e837f14720baa79f13))


## v2.7.0 (2025-02-02)

### Features


- Avoid protobuf repeated container overhead ([`4a99c14`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a99c14613c3243716e237d53816d821b12de2f4))


## v2.6.0 (2025-01-31)

### Features


- Update example to show how to use multiple devices ([`4a97019`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a97019bcf8baa7bfd4894d643d3f6c300de7603))


## v2.5.0 (2025-01-31)

### Features


- Reduce boilerplate in examples ([`03f3ff8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/03f3ff83d8f5719a53628d542a47e71988eb4599))


## v2.4.0 (2025-01-31)

### Features


- Simplify examples when using new habluetooth ([`1b38b3e`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1b38b3ef5f95b9df3fc3d71b123dadacd451852d))


## v2.3.0 (2025-01-31)

### Features


- Add example on connecting the scanner ([`b2d0eed`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/b2d0eedb5e22a448d41c2e65cfc4998a3e3972e2))


## v2.2.0 (2025-01-28)

### Features


- Add support for tracking bluetooth connection slot allocations ([`81fb130`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/81fb13001bf919962a26c51045c8acf4fd87f536))


## v2.1.1 (2025-01-22)

### Bug fixes


- Suppress duplicate connection changed callbacks ([`e3a5059`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/e3a505964ca3670e8f99450a4e33761026a5581b))


## v2.1.0 (2025-01-22)

### Features


- Update manager connection slot allocations on change ([`63045a7`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/63045a777088f28dded3c8e9f0a9959158af2348))


## v2.0.0 (2025-01-03)

### Bug fixes


- Move cache to device ([`2e44b28`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/2e44b284bc92967ccf1124dc9a78a9e04f0fb1f5))


### Refactoring


- Make wait_for_ble_connections_free require a timeout ([`72c0107`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/72c01078ed75686a8a6bd1ab0ed8243b0e69f99c))


## v1.1.1 (2024-12-22)

### Bug fixes


- Bump aioesphomeapi requirement to 27.0.0+ ([`1ab71d8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1ab71d812945c4d361272126b1c8bde68f171416))


### Unknown



## v1.1.0 (2024-10-05)

### Features


- Add support for python 3.13 ([`c3f2575`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c3f2575c9b942c1d89fb0f804b943678a6e75044))


## v1.0.0 (2024-02-18)

### Features


- Updates for aioesphomeapi 22 ([`c6a113a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c6a113a95313a22e47ccb6a1fda8c6e2e4b32850))


## v0.4.1 (2024-01-01)

### Performance improvements


- Avoid recreating enums from feature flags ([`00beb54`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/00beb54db075768069d9b48c1244866d2d402db2))


## v0.4.0 (2023-12-17)

### Features


- Add connect scanner helper ([`c4b110a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c4b110a6f3301af2d7a4bded236e2f5036a0d598))


## v0.3.0 (2023-12-14)

### Features


- Add available property to know when the esp device is connected ([`7732629`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/773262937fe106c573077a1f1d43156f00579f64))


## v0.2.0 (2023-12-13)

### Features


- Move mac_to_int helper to bluetooth_data_tools ([`79ff7da`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/79ff7da11cd360becf0e4c69c41c630d47b6fa13))


## v0.1.0 (2023-12-13)

### Features


- Initial import ([`7fa6be2`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/7fa6be28a475781ebd90e7e0060bb0890b68b29b))


## v0.0.0 (2023-12-06)
