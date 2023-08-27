{ python }:
python.pkgs.buildPythonPackage rec {
  name = "mk2";
  format = "flit";
  src = ./.;
  propagatedBuildInputs = with python.pkgs; [
    pyserial
    pyserial-asyncio
  ];
  nativeCheckInputs = with python.pkgs; [ pytestCheckHook ];
}
